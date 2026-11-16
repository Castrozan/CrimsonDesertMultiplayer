import capstone

MAXIMUM_XREFS_PER_ADDRESS = 12


def rip_relative_target(instruction):
    for operand in instruction.operands:
        if (
            operand.type == capstone.x86.X86_OP_MEM
            and operand.mem.base == capstone.x86.X86_REG_RIP
        ):
            return instruction.address + instruction.size + operand.mem.disp
    if instruction.group(capstone.CS_GRP_BRANCH_RELATIVE) or instruction.group(
        capstone.CS_GRP_CALL
    ):
        for operand in instruction.operands:
            if operand.type == capstone.x86.X86_OP_IMM:
                return operand.imm
    return None


def verified_reference_sites(image, target, limit=MAXIMUM_XREFS_PER_ADDRESS):
    sites = []
    for displacement_address in sorted(image.displacement_addresses_pointing_near(target)):
        function = image.function_containing(displacement_address)
        if function is None:
            continue
        for start in range(displacement_address - 1, displacement_address - 12, -1):
            instruction = image.instruction_at(start)
            if (
                instruction
                and start + instruction.size > displacement_address
                and rip_relative_target(instruction) == target
            ):
                sites.append(start)
                break
        if len(sites) >= limit:
            break
    return sites


