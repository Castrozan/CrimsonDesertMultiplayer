import collections
import re
import struct

from code_signatures import map_by_signature, map_within_function
from references import rip_relative_target, verified_reference_sites

MAXIMUM_NEARBY_DATA_DELTA = 0x80
MAXIMUM_VTABLE_SLOTS = 256


class AddressMapper:
    def __init__(self, old, new):
        self.old = old
        self.new = new
        self.cache = {}

    def map_code(self, relative_address, allow_callers=True):
        key = ("code", relative_address, allow_callers)
        if key in self.cache:
            return self.cache[key]
        self.cache[key] = (None, None)
        result = map_by_signature(self.old, self.new, relative_address)
        if result[0] is None:
            result = map_within_function(
                self.old,
                self.new,
                relative_address,
                lambda begin: self.map_code(begin, allow_callers)[0],
            )
        if result[0] is None and allow_callers:
            result = self.map_virtual_function(relative_address)
        if result[0] is None and allow_callers:
            result = self.map_by_references(relative_address, code_target=True)
        self.cache[key] = result
        return result

    def map_by_references(self, target, code_target):
        votes = collections.Counter()
        for site in verified_reference_sites(self.old, target):
            new_site, _ = self.map_code(site, allow_callers=False)
            if new_site is None:
                continue
            instruction = self.new.instruction_at(new_site)
            new_target = rip_relative_target(instruction) if instruction else None
            if new_target is not None:
                votes[new_target] += 1
        if not votes:
            return None, None
        ((winner, count),) = votes.most_common(1)
        total = sum(votes.values())
        if code_target and not self.new.is_code(winner):
            return None, None
        return winner, f"references {count}/{total}"

    def map_virtual_function(self, relative_address):
        votes = collections.Counter()
        pointer = re.escape(struct.pack("<Q", self.old.image_base + relative_address))
        for match in re.finditer(pointer, self.old.memory):
            if match.start() % 8:
                continue
            for slot in range(MAXIMUM_VTABLE_SLOTS):
                vtable = match.start() - 8 * slot
                new_vtable, _ = self.map_vtable(vtable)
                if new_vtable is None:
                    continue
                new_function = struct.unpack_from("<Q", self.new.memory, new_vtable + 8 * slot)[0]
                votes[new_function - self.new.image_base] += 1
                break
        if not votes:
            return None, None
        ((winner, count),) = votes.most_common(1)
        if not self.new.is_code(winner):
            return None, None
        return winner, f"vtable slot {count}/{sum(votes.values())}"

    def map_vtable(self, relative_address):
        locator_address = (
            struct.unpack_from("<Q", self.old.memory, relative_address - 8)[0]
            - self.old.image_base
        )
        if not 0 < locator_address < len(self.old.memory) - 24:
            return None, None
        signature, offset, _, type_descriptor = struct.unpack_from(
            "<IIII", self.old.memory, locator_address
        )
        if signature != 1 or not 0 < type_descriptor < len(self.old.memory) - 16:
            return None, None
        name_begin = type_descriptor + 16
        name = self.old.memory[name_begin : self.old.memory.index(b"\0", name_begin)]
        if not name.startswith(b".?A"):
            return None, None
        new_names = [
            m.start() for m in re.finditer(re.escape(name + b"\0"), self.new.memory)
        ]
        if len(new_names) != 1:
            return None, None
        new_type_descriptor = new_names[0] - 16
        locator_pattern = re.compile(
            re.escape(struct.pack("<III", 1, offset, 0)[:8]) + b"....", re.DOTALL
        )
        for match in re.finditer(
            re.escape(struct.pack("<I", new_type_descriptor)), self.new.memory
        ):
            locator = match.start() - 12
            if locator % 4 or not locator_pattern.match(self.new.memory, locator):
                continue
            pointer = struct.pack("<Q", self.new.image_base + locator)
            vtables = [
                m.start() + 8 for m in re.finditer(re.escape(pointer), self.new.memory)
            ]
            if len(vtables) == 1:
                return vtables[0], "rtti " + name.decode()
        return None, None

    def map_data(self, relative_address):
        result = self.map_vtable(relative_address)
        if result[0] is not None:
            return result
        result = self.map_by_references(relative_address, code_target=False)
        if result[0] is not None:
            return result
        for delta in range(8, MAXIMUM_NEARBY_DATA_DELTA + 1, 8):
            for base in (relative_address - delta, relative_address + delta):
                mapped, method = self.map_by_references(base, code_target=False)
                if mapped is not None:
                    return mapped + (
                        relative_address - base
                    ), f"{method} at {delta:+#x}"
        return None, None

    def map(self, relative_address):
        if self.old.is_code(relative_address):
            return self.map_code(relative_address)
        return self.map_data(relative_address)


