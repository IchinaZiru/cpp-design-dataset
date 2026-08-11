## Design Specification for RISC-V Instruction Parsing (F01/U01)

This document details the design specification for parsing and representing RISC-V instructions, based on the provided C++ header file (`Instruction.hpp`).  It is intended to guide the re-implementation of this functionality in another LLM without access to the original source code.

**1. Overview**

The core purpose of this module is to decode a 32-bit RISC-V instruction (represented as an `unsigned int`) into its constituent parts and provide a structured representation for further processing (e.g., simulation). The design utilizes a base class (`InstructionBase`) with derived classes for each major instruction type (R, I, S, B, U, J).

**2. Data Types & Definitions**

*   `Instruction`:  An alias for `unsigned int`, representing the raw 32-bit instruction word.
*   `Immediate`: This is an integer type used to store immediate values extracted from instructions. The underlying implementation in the provided code isn't explicitly defined, but it should be a suitable integer type (e.g., `int32_t`).
*   `enum Type { R, I, S, B, U, J }`:  An enumeration representing the different instruction types:
    *   **R**: Register-type instructions.
    *   **I**: Immediate-type instructions.
    *   **S**: Store instructions.
    *   **B**: Branch instructions.
    *   **U**: Upper immediate instructions.
    *   **J**: Jump instructions.

**3. Core Class: `InstructionBase`**

This is the base class for all instruction types. It contains common fields and methods.

*   **Member Variables:**
    *   `opcode`:  `unsigned int` - The opcode of the instruction.
    *   `rs1`: `unsigned int` - First source register number.
    *   `rs2`: `unsigned int` - Second source register number.
    *   `rd`: `unsigned int` - Destination register number.
    *   `funct3`: `unsigned int` - Function code (3 bits).
    *   `funct7`: `unsigned int` - Extended function code (7 bits).
    *   `imm`: `Immediate` - The immediate value of the instruction.
    *   `inst`: `Instruction` - The original, complete 32-bit instruction word.
    *   `t`: `Type` -  The type of the instruction (R, I, S, B, U, J).

*   **Constructors:**
    *   Default Constructor: Initializes all member variables to 0.
    *   Constructor with `unsigned int`: Sets opcode to `0b0010011`, t to `I`, and inst to -1.  Other members are initialized to 0. This appears to be a placeholder for a specific instruction (likely an immediate-type NOP).

*   **Static Methods:**
    *   `bin_mask(int digits)`: Returns a bitmask with the specified number of least significant bits set to 1.  Calculated as `(1 << digits) - 1`.
    *   `get_digits(unsigned int n, int hi, int lo)`: Extracts a range of bits from an unsigned integer `n`, starting at bit position `lo` and ending at bit position `hi` (inclusive). Uses the `bin_mask` function to isolate the desired bits.
    *   `expand_digit(unsigned int digit, int lo)`:  If `digit` is non-zero, returns a value with only the bit at position `lo` set; otherwise, returns 0. This is used for sign extension of immediate values.

*   **Methods:**
    *   `is_nop()`: Returns `true` if the instruction is considered a NOP (indicated by `inst == -1`), and `false` otherwise.
    *   `is_valid(const std::string &key)`: Checks if a given "key" (representing an instruction field like "imm", "rs2", etc.) is valid for the current instruction type.  Returns `true` if valid, `false` otherwise. The logic depends on the value of `t`:
        *   R: Invalid key is "imm".
        *   I: Invalid keys are "rs2" and "funct7".
        *   S: Invalid keys are "rd" and "funct7".
        *   B: Invalid keys are "rd" and "funct7".
        *   U & J: Invalid keys are "rs1", "rs2", "funct3", and "funct7".
    *   `verify(const std::string &key)`: Throws an `InvalidAccess` exception if `is_valid(key)` returns `false`.  This is a validation mechanism.
    *   `debug()`: Prints the instruction in hexadecimal format, along with a human-readable string representing the instruction type (e.g., "lui", "auipc", "jal", "load", "store", "addi", etc.). The specific strings printed depend on the `opcode` and `funct3` values.
    *   `has_op1()`: Returns true if the instruction is not of type U or J, false otherwise.
    *   `has_op2()`: Returns true if the instruction is of type R, S, or B, false otherwise.

**4. Derived Classes (InstructionR, InstructionI, InstructionS, InstructionB, InstructionU, InstructionJ)**

Each derived class represents a specific instruction type and inherits from `InstructionBase`.  The constructor for each class takes an `Instruction` as input and extracts the relevant fields by calling the static methods of `InstructionBase` (`get_digits`, `expand_digit`). The extracted values are then assigned to the corresponding member variables.

*   **Common Pattern:** Each derived class's constructor:
    1.  Calls `InstructionBase`’s default constructor (implicitly or explicitly).
    2.  Extracts fields from the input `inst` using `get_digits` and `expand_digit`.
    3.  Assigns extracted values to corresponding member variables in the base class.
    4.  Sets the `t` member variable to the appropriate instruction type (R, I, S, B, U, or J).

*   **Specific Field Extraction:** The specific bit ranges used in `get_digits` vary for each derived class based on the RISC-V instruction format. Refer to the provided code for exact details.  For example:
    *   `InstructionR`: Extracts `opcode`, `rd`, `funct3`, `rs1`, `rs2`, and `funct7`.
    *   `InstructionI`: Extracts `opcode`, `rd`, `funct3`, `rs1`, and `imm`.
    *   `InstructionS`: Extracts `opcode`, `funct3`, `rs1`, `rs2`, and `imm`.
    *   `InstructionB`: Extracts `opcode`, `funct3`, `rs1`, `rs2`, and `imm`.
    *   `InstructionU`: Extracts `opcode`, `rd`, and `imm`.
    *   `InstructionJ`: Extracts `opcode`, `rd`, and `imm`.

**5. Error Handling**

The `InstructionBase` class includes an `InvalidAccess` exception that is thrown by the `verify()` method when an invalid field access is attempted (as determined by `is_valid()`). This provides a mechanism for detecting errors during instruction parsing.

**6.  Assumptions & Clarifications**

*   The implementation of `Immediate` is not defined in the provided code, but it should be a suitable integer type to hold immediate values.
*   The bit positions and masks used in `get_digits` are crucial for correct decoding. These must be implemented accurately based on the RISC-V instruction format specification.
* The debug function relies on specific opcode/funct3 combinations to print meaningful output. This should be maintained during re-implementation.

This design specification provides a comprehensive overview of the functionality and structure of the provided C++ code, enabling its accurate re-implementation in another LLM environment.  The key is to faithfully reproduce the data structures, class hierarchies, static methods, and field extraction logic described above.
