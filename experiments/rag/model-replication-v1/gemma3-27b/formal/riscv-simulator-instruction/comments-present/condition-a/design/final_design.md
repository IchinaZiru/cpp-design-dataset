## Design Specification: RISC-V Instruction Parsing and Representation

This document details the design for a C++ library to parse and represent RISC-V instructions.  It is intended as a specification for another LLM to re-implement the functionality described in the provided `Instruction.hpp` file.

**1. Overview**

The library defines structures to represent RISC-V instructions, extracting relevant fields from an unsigned integer representing the instruction's binary encoding. It supports different instruction types (R, I, S, B, U, J) and provides methods for accessing individual fields and basic validation.

**2. Data Types**

*   `Instruction`:  An alias for `unsigned int`. Represents the raw 32-bit RISC-V instruction encoding.
*   `Immediate`: (Defined in Common.h - not provided, assume it's a type that can hold an integer value representing immediate data). This is used to store immediate values extracted from instructions.
*   `enum Type`: An enumeration defining the different RISC-V instruction types: `R`, `I`, `S`, `B`, `U`, and `J`.

**3. Classes & Structures**

**3.1. `InstructionBase` (Abstract Base Class)**

*   **Purpose:** Provides common functionality for all instruction types, including field extraction utilities and validation.
*   **Members:**
    *   `opcode`:  `unsigned int` - The opcode of the instruction.
    *   `rs1`: `unsigned int` - The first source register number.
    *   `rs2`: `unsigned int` - The second source register number.
    *   `rd`: `unsigned int` - The destination register number.
    *   `funct3`: `unsigned int` - The funct3 field of the instruction.
    *   `funct7`: `unsigned int` - The funct7 field of the instruction.
    *   `imm`: `Immediate` - The immediate value of the instruction.
    *   `inst`: `Instruction` - The original raw instruction value.
    *   `t`: `Type` -  The type of the instruction (R, I, S, B, U, J).

*   **Methods:**
    *   `InstructionBase()`: Default constructor. Initializes all members to 0 and sets `inst` to -1.
    *   `InstructionBase(unsigned)`: Constructor that initializes with a value and sets opcode to `0b0010011`, type to `I`, and inst to -1.
    *   `nop()`: Static method returning an `InstructionBase` representing the NOP (no operation) instruction.  This is achieved by creating an instance initialized with the default constructor.
    *   `is_nop()`: Returns `true` if the instruction is a NOP (i.e., `inst == -1`), otherwise returns `false`.
    *   `bin_mask(int digits)`: Static method that returns a bitmask with `digits` number of 1s.  Calculated as `(1 << digits) - 1`.
    *   `get_digits(unsigned int n, int hi, int lo)`: Static method to extract a range of bits from an unsigned integer. Returns the value of bits from `lo` (inclusive) to `hi` (inclusive).
    *   `expand_digit(unsigned int digit, int lo)`: Static method that expands a single bit into a 32-bit mask starting at position `lo`. If `digit` is non-zero, returns a mask with the specified bit set; otherwise, returns 0.
    *   `is_valid(const std::string &key)`:  Checks if a given field (`key`) is valid for the current instruction type. Returns `true` if valid, `false` otherwise. The validation rules are as follows:
        *   R-type: "imm" is invalid.
        *   I-type: "rs2" and "funct7" are invalid.
        *   S-type: "rd" and "funct7" are invalid.
        *   B-type: "rd" and "funct7" are invalid.
        *   U/J-type: "rs1", "rs2", "funct3", and "funct7" are invalid.
    *   `verify(const std::string &key)`:  Throws an `InvalidAccess` exception if the given field (`key`) is not valid for the current instruction type (using `is_valid`).
    *   `debug()`: Prints a human-readable representation of the instruction to standard output. It identifies NOP, LUI, AUIPC, JAL, JALR, branch, load, store and some R-type instructions based on opcode/funct3 values.  Prints "unknown" if it cannot identify the instruction type.
    *   `has_op1()`: Returns `true` if the instruction is not of U or J type; otherwise returns false.
    *   `has_op2()`: Returns `true` if the instruction is R, S, or B type; otherwise returns false.

**3.2. `InstructionR` (Derived from `InstructionBase`)**

*   **Purpose:** Represents an R-type instruction.
*   **Constructor:**  Takes an `Instruction` as input and extracts fields using the methods of `InstructionBase`.
    *   `opcode`: Bits 6-0
    *   `rd`: Bits 11-7
    *   `funct3`: Bits 14-12
    *   `rs1`: Bits 19-15
    *   `rs2`: Bits 24-20
    *   `funct7`: Bits 31-25

**3.3. `InstructionI` (Derived from `InstructionBase`)**

*   **Purpose:** Represents an I-type instruction.
*   **Constructor:** Takes an `Instruction` as input and extracts fields using the methods of `InstructionBase`.
    *   `opcode`: Bits 6-0
    *   `rd`: Bits 11-7
    *   `funct3`: Bits 14-12
    *   `rs1`: Bits 19-15
    *   `imm`: Bits 30-20, combined with the sign-extended bit 31 (shifted to position 11).

**3.4. `InstructionS` (Derived from `InstructionBase`)**

*   **Purpose:** Represents an S-type instruction.
*   **Constructor:** Takes an `Instruction` as input and extracts fields using the methods of `InstructionBase`.
    *   `opcode`: Bits 6-0
    *   `funct3`: Bits 14-12
    *   `rs1`: Bits 19-15
    *   `rs2`: Bits 24-20
    *   `imm`:  Bits 11-7, combined with bits 30-25 (shifted left by 5), and the sign-extended bit 31 (shifted to position 11).

**3.5. `InstructionB` (Derived from `InstructionBase`)**

*   **Purpose:** Represents a B-type instruction.
*   **Constructor:** Takes an `Instruction` as input and extracts fields using the methods of `InstructionBase`.
    *   `opcode`: Bits 6-0
    *   `funct3`: Bits 14-12
    *   `rs1`: Bits 19-15
    *   `rs2`: Bits 24-20
    *   `imm`:  Bits 11-8 (shifted left by 1), combined with bits 30-25 (shifted left by 5), bit 7 (shifted left by 11) and the sign-extended bit 31 (shifted to position 12).

**3.6. `InstructionU` (Derived from `InstructionBase`)**

*   **Purpose:** Represents a U-type instruction.
*   **Constructor:** Takes an `Instruction` as input and extracts fields using the methods of `InstructionBase`.
    *   `opcode`: Bits 6-0
    *   `rd`: Bits 11-7
    *   `imm`:  Bits 19-12 (shifted left by 12), combined with bits 30-20 (shifted left by 20) and bit 31 (shifted left by 31).

**3.7. `InstructionJ` (Derived from `InstructionBase`)**

*   **Purpose:** Represents a J-type instruction.
*   **Constructor:** Takes an `Instruction` as input and extracts fields using the methods of `InstructionBase`.
    *   `opcode`: Bits 6-0
    *   `rd`: Bits 11-7
    *   `imm`:  Bits 30-21 (shifted left by 1), combined with bit 20 (shifted left by 11), bits 19-12 (shifted left by 12) and the sign-extended bit 31 (shifted to position 20).

**4. Error Handling**

*   The `verify()` method in `InstructionBase` throws an exception of type `InvalidAccess` if a field is invalid for the instruction type.

**5. Dependencies**

*   `<utility>`
*   `Common.h` (defines `Immediate`)
*   `<string>`
*   `<iostream>`

This specification provides a comprehensive overview of the functionality and structure of the RISC-V instruction parsing library, enabling another LLM to accurately re-implement it based on this design document.  It focuses solely on the provided code and avoids making assumptions about missing information.
