import bisect

import capstone
import numpy
import pefile

IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_WRITE = 0x80000000


class Image:
    def __init__(self, path):
        portable_executable = pefile.PE(path, fast_load=True)
        portable_executable.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"]]
        )
        self.image_base = portable_executable.OPTIONAL_HEADER.ImageBase
        self.timestamp = portable_executable.FILE_HEADER.TimeDateStamp
        self.memory = bytes(portable_executable.get_memory_mapped_image())
        self.sections = [
            (
                section.VirtualAddress,
                section.VirtualAddress + section.Misc_VirtualSize,
                section.Characteristics,
            )
            for section in portable_executable.sections
        ]
        self.code_begin, self.code_end, _ = max(
            (s for s in self.sections if s[2] & IMAGE_SCN_MEM_EXECUTE and not s[2] & IMAGE_SCN_MEM_WRITE),
            key=lambda s: s[1] - s[0],
        )
        self.code = memoryview(self.memory)[self.code_begin : self.code_end]
        functions = sorted(
            (entry.struct.BeginAddress, entry.struct.EndAddress)
            for entry in portable_executable.DIRECTORY_ENTRY_EXCEPTION
        )
        self.function_begins = [begin for begin, _ in functions]
        self.function_ends = [end for _, end in functions]
        self.disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.disassembler.detail = True

    def is_code(self, relative_address):
        return self.code_begin <= relative_address < self.code_end

    def function_containing(self, relative_address):
        index = bisect.bisect_right(self.function_begins, relative_address) - 1
        if index < 0 or relative_address >= self.function_ends[index]:
            return None
        return self.function_begins[index], self.function_ends[index]

    def instructions(self, begin, end):
        return list(self.disassembler.disasm(self.memory[begin:end], begin))

    def instruction_at(self, relative_address):
        decoded = self.instructions(relative_address, relative_address + 16)
        return (
            decoded[0] if decoded and decoded[0].address == relative_address else None
        )

    def count_matches(self, pattern, limit=2):
        found = []
        for match in pattern.finditer(self.code):
            found.append(self.code_begin + match.start())
            if len(found) >= limit:
                break
        return found

    def displacement_addresses_pointing_near(self, target, slack=4, chunk_elements=1 << 22):
        for alignment in range(4):
            usable = (len(self.code) - alignment) // 4 * 4
            displacements = numpy.frombuffer(self.code, dtype="<i4", count=usable // 4, offset=alignment)
            for chunk_begin in range(0, len(displacements), chunk_elements):
                chunk = displacements[chunk_begin : chunk_begin + chunk_elements].astype(numpy.int64)
                addresses = self.code_begin + alignment + 4 * (numpy.arange(len(chunk), dtype=numpy.int64) + chunk_begin)
                pointed = addresses + 4 + chunk
                for index in numpy.flatnonzero((pointed >= target - slack) & (pointed <= target)):
                    yield int(addresses[index])
