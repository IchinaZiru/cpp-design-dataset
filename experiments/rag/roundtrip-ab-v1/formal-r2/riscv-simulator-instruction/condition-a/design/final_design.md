### Design Specification for Reimplementation of `Instruction.hpp`

#### Overview

This document provides a detailed design specification for the reimplementation of the `Instruction.hpp` file, which is part of an RISC-V simulator. The primary focus is on the `InstructionBase` class and its derived classes (`InstructionR`, `InstructionI`, `InstructionS`, `InstructionB`, `InstructionU`, `InstructionJ`). This document will outline the necessary components, their functionalities, and the relationships between them.

#### File Details

- **Path**: `src/Common/Instruction.hpp`
- **Role**: Complete target-owned implementation/declaration file
- **Replacement Required**: True

#### Dependencies

- `<utility>`
- `"Common.h"`
- `<string>`
- `<iostream>`

#### Type Definitions

- **Instruction**: `unsigned int` - Represents the raw instruction bits.

#### Classes and Structures

##### InstructionBase

**Description**: 
The base class for all RISC-V instructions. It contains common fields and methods used by all instruction types.

**Fields**:
- `opcode`: The opcode of the instruction.
- `rs1`, `rs2`, `rd`: Source and destination register indices.
- `funct3`, `funct7`: Function codes specific to certain instruction types.
- `imm`: Immediate value associated with the instruction.
- `inst`: Raw instruction bits.
- `t`: Type of the instruction (R, I, S, B, U, J).

**Enumerations**:
- **Type**: Enumerates the different types of RISC-V instructions.

**Methods**:
- **Constructors**:
  - Default constructor initializes all fields to zero and sets `inst` to 0.
  - Parameterized constructor initializes fields with default values for type I and sets `inst` to -1.
  
- **Static Methods**:
  - `nop()`: Returns a no-operation instruction.
  - `bin_mask(int digits)`: Generates a bitmask of the specified number of bits.
  - `get_digits(unsigned int n, int hi, int lo)`: Extracts a range of bits from an integer.
  - `expand_digit(unsigned int digit, int lo)`: Expands a single bit to fill all higher bits.

- **Instance Methods**:
  - `is_nop()`: Checks if the instruction is a no-operation.
  - `is_valid(const std::string &key)`: Validates whether a specific field is valid for the instruction type.
  - `verify(const std::string &key)`: Throws an exception if a field is invalid.
  - `debug()`: Prints debug information about the instruction.
  - `has_op1()`: Checks if the instruction has the first operand.
  - `has_op2()`: Checks if the instruction has the second operand.

**Nested Classes**:
- **InvalidAccess**: A class representing an exception for invalid field access.

##### InstructionR

**Description**: 
Represents R-type instructions, which use three registers and a function code.

**Constructor**:
- Takes an `Instruction` object and extracts relevant fields using `get_digits`.

##### InstructionI

**Description**: 
Represents I-type instructions, which use one register, an immediate value, and a function code.

**Constructor**:
- Takes an `Instruction` object and extracts relevant fields using `get_digits`. The immediate value is constructed by combining two parts and expanding the sign bit if necessary.

##### InstructionS

**Description**: 
Represents S-type instructions, which use two registers and an immediate value for storing data to memory.

**Constructor**:
- Takes an `Instruction` object and extracts relevant fields using `get_digits`. The immediate value is constructed by combining three parts and expanding the sign bit if necessary.

##### InstructionB

**Description**: 
Represents B-type instructions, which use two registers and a branch offset for conditional jumps.

**Constructor**:
- Takes an `Instruction` object and extracts relevant fields using `get_digits`. The immediate value is constructed by combining four parts and expanding the sign bit if necessary.

##### InstructionU

**Description**: 
Represents U-type instructions, which use one register and a large immediate value for loading data into registers.

**Constructor**:
- Takes an `Instruction` object and extracts relevant fields using `get_digits`. The immediate value is constructed by combining three parts and expanding the sign bit if necessary.

##### InstructionJ

**Description**: 
Represents J-type instructions, which use one register and a jump offset for unconditional jumps.

**Constructor**:
- Takes an `Instruction` object and extracts relevant fields using `get_digits`. The immediate value is constructed by combining four parts and expanding the sign bit if necessary.

#### Usage Example

```cpp
#include "Instruction.hpp"

int main() {
    Instruction inst = 0x00100093; // Example instruction: addi x5, x6, 19
    InstructionI i_inst(inst);
    
    i_inst.debug(); // Output: addi
    
    return 0;
}
```

#### Conclusion

This design specification provides a comprehensive guide for reimplementing the `Instruction.hpp` file. It covers all necessary components and their interactions, ensuring that the reimplementation adheres to the original structure and functionality while preserving the target-owned identifiers and namespaces.