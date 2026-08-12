# Memory Class Design Specification

## Overview
This document specifies the design of the `Memory` class, which provides a simple memory management system for reading and writing data at specific addresses. The class is designed to be used in systems where memory access needs to be controlled and validated.

## Class Structure

### Public Members
1. **mem**: An array of unsigned characters representing the memory space.
   - Type: `unsigned char[]`
   - Size: Defined by `MEMORY_SIZE` (opaque identifier, must be preserved)
2. **placeholder**: A placeholder value used when accessing invalid addresses.
   - Type: `unsigned char`

### Constructor
- **Memory()**
  - Initializes the memory array with zeros using `memset`.

## Methods

### Address Validation
1. **check_addr(unsigned int addr)**
   - Returns `true` if the address is within valid bounds (0 ≤ addr < MEMORY_SIZE), otherwise `false`.
   - Parameters:
     - `addr`: The address to check.
   - Return Type: `bool`

### Word Operations
2. **read_word(unsigned int addr)**
   - Reads a word (Immediate type) from the specified address.
   - Returns 0 if the address is invalid.
   - Parameters:
     - `addr`: The address to read from.
   - Return Type: `Immediate`
3. **write_word(unsigned int addr, Immediate imm)**
   - Writes a word (Immediate type) to the specified address.
   - Does nothing if the address is invalid.
   - Parameters:
     - `addr`: The address to write to.
     - `imm`: The value to write.

### Unsigned Short Operations
4. **read_ushort(unsigned int addr)**
   - Reads an unsigned short from the specified address.
   - Returns 0 if the address is invalid.
   - Parameters:
     - `addr`: The address to read from.
   - Return Type: `unsigned short`
5. **write_ushort(unsigned int addr, unsigned short imm)**
   - Writes an unsigned short to the specified address.
   - Does nothing if the address is invalid.
   - Parameters:
     - `addr`: The address to write to.
     - `imm`: The value to write.

### Array Access Operator
6. **operator[](unsigned int addr)**
   - Provides array-like access to memory.
   - Returns a reference to the placeholder if the address is invalid.
   - Parameters:
     - `addr`: The address to access.
   - Return Type: `unsigned char&`

### Debugging
7. **debug()**
   - Outputs a hexadecimal dump of memory from address 0x20000-0x10 to 0x20000.
   - Uses `std::cout` for output.

## Implementation Notes
- The class uses pointer arithmetic for reading and writing data at specific addresses.
- All methods include bounds checking via the `check_addr` method.
- The `debug` method is hardcoded to display a specific range of memory (0x20000-0x10 to 0x20000).

## Dependencies
- `<cstring>` for `memset`
- `<iostream>` for `std::cout` in the debug method

## Preserved Identifiers
- `MEMORY_SIZE`: Opaque identifier defining the size of the memory array.
- `Immediate`: Opaque type used for word operations.

This specification provides all necessary information to reimplement the `Memory` class while preserving the original structure and behavior.