import argparse
import collections
import difflib

import capstone

from address_mapper import AddressMapper
from code_signatures import instruction_token
from executable_image import Image
from references import verified_reference_sites


def memory_displacements(instruction):
    return [
        operand.mem.disp
        for operand in instruction.operands
        if operand.type == capstone.x86.X86_OP_MEM
        and operand.mem.base not in (0, capstone.x86.X86_REG_RIP)
    ]


def displacement_pairs(old, new, old_function, new_function_begin):
    new_function = new.function_containing(new_function_begin)
    if new_function is None:
        return []
    old_instructions = old.instructions(*old_function)
    new_instructions = new.instructions(*new_function)
    matcher = difflib.SequenceMatcher(
        None,
        [instruction_token(i).split("[")[0] for i in old_instructions],
        [instruction_token(i).split("[")[0] for i in new_instructions],
        autojunk=False,
    )
    pairs = []
    for tag, old_low, old_high, new_low, new_high in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset in range(old_high - old_low):
            old_displacements = memory_displacements(old_instructions[old_low + offset])
            new_displacements = memory_displacements(new_instructions[new_low + offset])
            if len(old_displacements) == len(new_displacements):
                pairs.extend(zip(old_displacements, new_displacements))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="Report how struct field offsets moved between two builds."
    )
    parser.add_argument("old_executable")
    parser.add_argument("new_executable")
    parser.add_argument(
        "--functions", nargs="*", default=[], help="old function addresses, hex"
    )
    parser.add_argument(
        "--referencing",
        nargs="*",
        default=[],
        help="old globals whose referencing functions are used, hex",
    )
    parser.add_argument(
        "--offsets", nargs="+", required=True, help="old field offsets of interest, hex"
    )
    arguments = parser.parse_args()
    old = Image(arguments.old_executable)
    new = Image(arguments.new_executable)
    mapper = AddressMapper(old, new)
    functions = {old.function_containing(int(text, 16)) for text in arguments.functions}
    for text in arguments.referencing:
        functions.update(
            old.function_containing(site)
            for site in verified_reference_sites(old, int(text, 16), limit=40)
        )
    interesting = {int(text, 16) for text in arguments.offsets}
    votes = collections.defaultdict(collections.Counter)
    for function in filter(None, functions):
        new_begin, _ = mapper.map_code(function[0], allow_callers=False)
        if new_begin is None:
            continue
        for old_displacement, new_displacement in displacement_pairs(
            old, new, function, new_begin
        ):
            if old_displacement in interesting:
                votes[old_displacement][new_displacement] += 1
    for offset in sorted(interesting):
        print(
            hex(offset),
            {hex(k): v for k, v in votes[offset].most_common(4)} or "no evidence",
        )


if __name__ == "__main__":
    main()
