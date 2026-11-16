import argparse
import json
import sys

from address_mapper import AddressMapper
from executable_image import Image


def main():
    parser = argparse.ArgumentParser(
        description="Map relative addresses from one build of an executable to another."
    )
    parser.add_argument("old_executable")
    parser.add_argument("new_executable")
    parser.add_argument(
        "addresses",
        nargs="+",
        help="relative addresses in hex, or @file with one per line",
    )
    arguments = parser.parse_args()
    addresses = []
    for item in arguments.addresses:
        if item.startswith("@"):
            with open(item[1:]) as handle:
                addresses.extend(line.split()[0] for line in handle if line.strip())
        else:
            addresses.append(item)
    old = Image(arguments.old_executable)
    new = Image(arguments.new_executable)
    mapper = AddressMapper(old, new)
    for text in addresses:
        relative_address = int(text, 16)
        mapped, method = mapper.map(relative_address)
        print(
            json.dumps(
                {
                    "old": hex(relative_address),
                    "new": hex(mapped) if mapped is not None else None,
                    "kind": "code" if old.is_code(relative_address) else "data",
                    "method": method,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    sys.exit(main())
