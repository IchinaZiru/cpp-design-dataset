### Design Specification for Reimplementation of `Instruction.hpp`

#### Overview

This document provides a detailed design specification for the reimplementation of the `Instruction.hpp` file. The primary goal is to ensure that the new implementation adheres strictly to the structure, functionality, and behavior defined in the original source code.

#### File Details

- **Path**: `src/Common/Instruction.hpp`
- **Role**: Complete target-owned implementation/declaration file
- **Replacement Required**: True

#### Dependencies

The following dependencies must be preserved:

- `<utility>`
- `"Common.h"`
- `<string>`
- `<iostream>`

#### Constants and Types

1. **Instruction Type**:
   - `using Instruction = unsigned int;`
   
2. **Immediate Type**:
   - The type `Immediate` is assumed to be defined in `"Common.h"`.

3. **Enum Type**:
   ```cpp
   enum Type {
       R, I, S, B, U, J
   };
   ```

#### Classes and Structures

1. **InstructionBase**

   - **Purpose**: Base class for all instruction types.
   
   - **Members**:
     - `unsigned opcode, rs1, rs2, rd, funct3, funct7;`
     - `Immediate imm;`
     - `Instruction inst;`
     - `enum Type t;`
     
   - **Constructors**:
     - Default Constructor: Initializes all fields to zero and sets `inst` to 0.
     - Parameterized Constructor (`unsigned`): Sets default values for R-type instructions, initializes `opcode` to `0b0010011`, `t` to `I`, and `inst` to `-1`.
     
   - **Static Methods**:
     - `static InstructionBase nop()`: Returns an instance of `InstructionBase` representing a NOP instruction.
     - `static constexpr unsigned int bin_mask(int digits)`: Computes a bitmask for the specified number of bits.
     - `static unsigned int get_digits(unsigned int n, int hi, int lo)`: Extracts a range of bits from `n`.
     - `static unsigned int expand_digit(unsigned int digit, int lo)`: Expands a single bit to fill all higher bits starting from position `lo`.
     
   - **Member Methods**:
     - `bool is_nop()`: Checks if the instruction is a NOP.
     - `bool is_valid(const std::string &key)`: Validates whether a specific field (`key`) is valid for the current instruction type.
     - `void verify(const std::string &key)`: Throws an exception if the specified field is not valid.
     - `void debug()`: Prints a human-readable representation of the instruction to `std::cout`.
     - `bool has_op1()`: Checks if the instruction has operand 1.
     - `bool has_op2()`: Checks if the instruction has operand 2.

   - **Nested Classes**:
     - `class InvalidAccess`: Placeholder for exception handling related to invalid access of instruction fields.

2. **InstructionR**

   - **Purpose**: Represents R-type instructions.
   
   - **Constructor**:
     - Takes an `Instruction` and extracts relevant fields using `get_digits`.

3. **InstructionI**

   - **Purpose**: Represents I-type instructions.
   
   - **Constructor**:
     - Takes an `Instruction` and extracts relevant fields using `get_digits`. The immediate value is constructed by combining bits from different positions.

4. **InstructionS**

   - **Purpose**: Represents S-type instructions.
   
   - **Constructor**:
     - Takes an `Instruction` and extracts relevant fields using `get_digits`. The immediate value is constructed by combining bits from different positions.

5. **InstructionB**

   - **Purpose**: Represents B-type instructions.
   
   - **Constructor**:
     - Takes an `Instruction` and extracts relevant fields using `get_digits`. The immediate value is constructed by combining bits from different positions, including sign extension.

6. **InstructionU**

   - **Purpose**: Represents U-type instructions.
   
   - **Constructor**:
     - Takes an `Instruction` and extracts relevant fields using `get_digits`. The immediate value is constructed by combining bits from different positions, including sign extension.

7. **InstructionJ**

   - **Purpose**: Represents J-type instructions.
   
   - **Constructor**:
     - Takes an `Instruction` and extracts relevant fields using `get_digits`. The immediate value is constructed by combining bits from different positions, including sign extension.

#### Usage

- The `InstructionBase` class serves as a base for all instruction types, providing common functionality such as field extraction, validation, and debugging.
- Derived classes (`InstructionR`, `InstructionI`, etc.) are responsible for parsing specific instruction formats and initializing the appropriate fields in the base class.

#### Conclusion

This design specification provides a comprehensive guide for reimplementing the `Instruction.hpp` file. The new implementation should strictly adhere to the structure, functionality, and behavior defined here to ensure compatibility with existing systems that depend on this code.