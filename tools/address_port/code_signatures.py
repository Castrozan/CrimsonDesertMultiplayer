import difflib
import re

import capstone

MAXIMUM_SIGNATURE_INSTRUCTIONS = 48


def masked_bytes(instruction, loose):
    data = bytearray(instruction.bytes)
    mask = [True] * len(data)

    def wildcard(offset, size):
        for index in range(offset, offset + size):
            if 0 <= index < len(mask):
                mask[index] = False

    has_relative_memory = any(
        operand.type == capstone.x86.X86_OP_MEM
        and operand.mem.base == capstone.x86.X86_REG_RIP
        for operand in instruction.operands
    )
    is_relative_branch = instruction.group(capstone.CS_GRP_BRANCH_RELATIVE) or (
        instruction.group(capstone.CS_GRP_CALL) and instruction.imm_size
    )
    if has_relative_memory or (loose and instruction.disp_size > 1):
        wildcard(instruction.disp_offset, instruction.disp_size)
    if is_relative_branch and instruction.imm_size:
        wildcard(instruction.imm_offset, instruction.imm_size)
    if loose and instruction.imm_size > 1:
        wildcard(instruction.imm_offset, instruction.imm_size)
    if loose and instruction.disp_size == 1 and not has_relative_memory:
        wildcard(instruction.disp_offset, 1)
    return list(zip(data, mask))


def compile_signature(masked):
    expression = b"".join(
        re.escape(bytes([value])) if keep else b"." for value, keep in masked
    )
    return re.compile(expression, re.DOTALL)


def unique_forward_signature(image, relative_address, loose):
    decoded = image.instructions(
        relative_address, relative_address + 16 * MAXIMUM_SIGNATURE_INSTRUCTIONS
    )
    if not decoded or decoded[0].address != relative_address:
        return None
    masked = []
    for count, instruction in enumerate(
        decoded[:MAXIMUM_SIGNATURE_INSTRUCTIONS], start=1
    ):
        masked.extend(masked_bytes(instruction, loose))
        if len(masked) < 16:
            continue
        pattern = compile_signature(masked)
        if image.count_matches(pattern) == [relative_address]:
            return pattern
    return None


def map_by_signature(old, new, relative_address):
    for loose in (False, True):
        pattern = unique_forward_signature(old, relative_address, loose)
        if pattern is None:
            continue
        matches = new.count_matches(pattern)
        if len(matches) == 1:
            return matches[0], "signature-loose" if loose else "signature"
    return None, None


def instruction_token(instruction):
    operands = re.sub(r"0x[0-9a-f]{3,}", "#", instruction.op_str)
    return instruction.mnemonic + " " + operands


def map_within_function(old, new, relative_address, function_mapper):
    old_function = old.function_containing(relative_address)
    if old_function is None or old_function[0] == relative_address:
        return None, None
    new_function_begin = function_mapper(old_function[0])
    if new_function_begin is None:
        return None, None
    new_function = new.function_containing(new_function_begin)
    if new_function is None or new_function[0] != new_function_begin:
        return None, None
    old_instructions = old.instructions(*old_function)
    new_instructions = new.instructions(*new_function)
    index = next(
        (
            i
            for i, ins in enumerate(old_instructions)
            if ins.address == relative_address
        ),
        None,
    )
    if index is None:
        return None, None
    matcher = difflib.SequenceMatcher(
        None,
        [instruction_token(i) for i in old_instructions],
        [instruction_token(i) for i in new_instructions],
        autojunk=False,
    )
    for tag, old_low, old_high, new_low, new_high in matcher.get_opcodes():
        if tag == "equal" and old_low <= index < old_high:
            return new_instructions[new_low + index - old_low].address, "function-diff"
    return None, None


