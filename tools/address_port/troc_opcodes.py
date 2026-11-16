import argparse
import json
import re
import struct

from executable_image import Image

TROC_KIND_OFFSET = 0x08
TROC_OPCODE_OFFSET = 0x0C
INITIALIZER_STORE = re.compile(rb"\x48\x8d\x05(.{4})\x48\x89\x05(.{4})", re.DOTALL)


def rtti_name(image, vtable):
    locator = struct.unpack_from("<Q", image.memory, vtable - 8)[0] - image.image_base
    if not 0 < locator < len(image.memory) - 16:
        return None
    signature, _, _, type_descriptor = struct.unpack_from(
        "<IIII", image.memory, locator
    )
    if signature != 1 or not 0 < type_descriptor < len(image.memory) - 16:
        return None
    name_begin = type_descriptor + 16
    name = image.memory[name_begin : image.memory.find(b"\0", name_begin)]
    return name.decode() if name.startswith(b".?A") else None


def vtables_stored_by_initializers(image):
    stored = {}
    for match in INITIALIZER_STORE.finditer(image.code):
        lea_end = image.code_begin + match.start() + 7
        vtable = lea_end + struct.unpack_from("<i", match.group(1))[0]
        stored.setdefault(lea_end + 7 + struct.unpack_from("<i", match.group(2))[0], vtable)
    return stored


def troc_messages(image, begin, end):
    stored = vtables_stored_by_initializers(image)
    messages = {}
    for address in range(begin, end, 8):
        vtable = stored.get(address)
        name = rtti_name(image, vtable) if vtable is not None else None
        if name is None:
            continue
        kind, opcode = struct.unpack_from("<IH", image.memory, address + TROC_KIND_OFFSET)
        messages.setdefault(name, (kind, opcode))
    return messages


def main():
    parser = argparse.ArgumentParser(
        description="Translate message opcodes between two builds through their RTTI names."
    )
    parser.add_argument("old_executable")
    parser.add_argument(
        "old_range", help="begin:end of the old build's static message instances, hex"
    )
    parser.add_argument("new_executable")
    parser.add_argument(
        "new_range", help="begin:end of the new build's static message instances, hex"
    )
    arguments = parser.parse_args()
    tables = []
    for path, span in (
        (arguments.old_executable, arguments.old_range),
        (arguments.new_executable, arguments.new_range),
    ):
        begin, end = (int(part, 16) for part in span.split(":"))
        tables.append(troc_messages(Image(path), begin, end))
    old_messages, new_messages = tables
    for name, (kind, opcode) in sorted(
        old_messages.items(), key=lambda item: item[1][1]
    ):
        new_kind, new_opcode = new_messages.get(name, (None, None))
        print(
            json.dumps(
                {
                    "name": name,
                    "kind": kind,
                    "old": opcode,
                    "new": new_opcode,
                    "new_kind": new_kind,
                }
            )
        )


if __name__ == "__main__":
    main()
