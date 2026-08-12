# Design Specification for RISC-V Instruction Decoder

## Overview
This document specifies the design of a RISC-V instruction decoder implementation in C++. The code provides structures to parse and analyze RISC-V machine instructions, categorizing them into different types (R, I, S, B, U, J) and extracting their components.

## Core Components

### 1. Basic Types
- `Instruction`: Alias for `unsigned int` representing a raw instruction word
- `Immediate`: Type for immediate values (exact definition not specified in input)

### 2. InstructionBase Structure
The base class containing common fields and methods for all instruction types.

#### Fields:
- `opcode`: 7-bit operation code
- `rs1`, `rs2`, `rd`: Source/destination register specifiers (5 bits each)
- `funct3`, `funct7`: Function codes (3 and 7 bits respectively)
- `imm`: Immediate value field
- `inst`: The raw instruction word
- `t`: Instruction type enum (R, I, S, B, U, J)

#### Methods:
- Constructors for default and NOP instructions
- `is_nop()`: Checks if instruction is a NOP
- `bin_mask(digits)`: Creates bitmask of given width
- `get_digits(n, hi, lo)`: Extracts bits from position hi to lo
- `expand_digit(digit, lo)`: Expands sign bit to full immediate
- `is_valid(key)`: Validates field access for instruction type
- `verify(key)`: Throws exception if field access is invalid
- `debug()`: Prints human-readable instruction representation
- `has_op1()`, `has_op2()`: Checks operand presence

### 3. Instruction Type Derivatives
Six derived structures implementing specific instruction formats:

#### InstructionR (Register-type)
- Extracts opcode, rd, funct3, rs1, rs2, funct7 from bits [6:0], [11:7], [14:12], [19:15], [24:20], [31:25]

#### InstructionI (Immediate-type)
- Extracts opcode, rd, funct3, rs1 from same positions as R-type
- Constructs immediate from bits [30:20] and sign-extended bit [31]

#### InstructionS (Store-type)
- Similar to I-type but with rs2 instead of rd
- Immediate constructed from bits [11:7], [30:25], and sign extension

#### InstructionB (Branch-type)
- Extracts funct3, rs1, rs2 like R-type
- Complex immediate construction using bits [11:8], [30:25], [7:7], with sign extension

#### InstructionU (Upper Immediate-type)
- For LUI/AUIPC instructions
- Constructs 32-bit immediate from bits [19:12], [30:20], and [31]

#### InstructionJ (Jump-type)
- Similar to U-type but for JAL/JALR
- Complex immediate construction using bits [30:21], [20:20], [19:12], with sign extension

## Implementation Notes

1. **Instruction Parsing**:
   - Each derived class implements a constructor that takes an `Instruction` and parses it into components
   - The parsing logic is specific to each instruction format

2. **Error Handling**:
   - Invalid field access throws `InvalidAccess` exception
   - Field validity depends on instruction type (e.g., I-type instructions don't have rs2)

3. **Debugging Support**:
   - `debug()` method provides human-readable output
   - Recognizes common opcodes and prints mnemonic names

4. **Type Safety**:
   - The `t` field tracks instruction type
   - Field access validation prevents misuse of instruction components

## Usage Pattern

1. Create an `Instruction` from raw machine code
2. Determine instruction type (based on opcode)
3. Construct appropriate derived class instance:
   ```cpp
   InstructionR r_inst(raw_instruction);
   InstructionI i_inst(raw_instruction);
   // etc.
   ```
4. Access components through public fields after verifying validity

## Dependencies
- `<utility>` for pair/tuple support (though not directly used in shown code)
- `"Common.h"` (contents unspecified)
- `<string>` and `<iostream>` for debugging output

This specification provides all necessary information to reimplement the instruction decoder while preserving the original structure, naming conventions, and behavior.