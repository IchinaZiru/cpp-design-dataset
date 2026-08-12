# Memory Class Design Specification

## Overview
This document specifies the design of the `Memory` class, which provides memory management functionality for a system. The class handles reading and writing operations at different granularities (byte, word, unsigned short) with bounds checking.

## Class Structure

### Public Members
- **mem**: Array of `unsigned char` of size `MEMORY_SIZE`
  - Primary storage for the memory contents
- **placeholder**: Single `unsigned char` used as a fallback return value when accessing invalid addresses

### Constructor
```cpp
Memory()
```
- Initializes all elements in `mem` to zero using `memset`

## Methods

### Address Validation
```cpp
bool check_addr(unsigned int addr)
```
- **Purpose**: Validates if an address is within bounds of the memory array
- **Parameters**:
  - `addr`: The address to validate (unsigned integer)
- **Returns**:
  - `true` if address is valid (0 ≤ addr < MEMORY_SIZE)
  - `false` otherwise
- **Note**: Contains commented-out assertion that could be enabled for debugging

### Word Operations
```cpp
Immediate read_word(unsigned int addr)
```
- **Purpose**: Reads a word (4 bytes) from memory at given address
- **Parameters**:
  - `addr`: Starting address of the word to read
- **Returns**:
  - The word value as `Immediate` type if address is valid
  - 0 if address is invalid

```cpp
void write_word(unsigned int addr, Immediate imm)
```
- **Purpose**: Writes a word (4 bytes) to memory at given address
- **Parameters**:
  - `addr`: Starting address for the write operation
  - `imm`: The word value to write as `Immediate` type

### Unsigned Short Operations
```cpp
unsigned short read_ushort(unsigned int addr)
```
- **Purpose**: Reads an unsigned short (2 bytes) from memory at given address
- **Parameters**:
  - `addr`: Starting address of the unsigned short to read
- **Returns**:
  - The unsigned short value if address is valid
  - 0 if address is invalid

```cpp
void write_ushort(unsigned int addr, unsigned short imm)
```
- **Purpose**: Writes an unsigned short (2 bytes) to memory at given address
- **Parameters**:
  - `addr`: Starting address for the write operation
  - `imm`: The unsigned short value to write

### Array Access Operator
```cpp
unsigned char &operator[](unsigned int addr)
```
- **Purpose**: Provides array-like access to memory with bounds checking
- **Parameters**:
  - `addr`: Address to access
- **Returns**:
  - Reference to the byte at given address if valid
  - Reference to `placeholder` if address is invalid

### Debug Method
```cpp
void debug()
```
- **Purpose**: Outputs a hex dump of memory in range [0x20000-0x10, 0x20000]
- **Output**:
  - Prints each byte as hexadecimal value separated by spaces
  - Ends with newline

## Implementation Notes
1. All read operations return zero for invalid addresses rather than throwing exceptions
2. Write operations silently fail for invalid addresses (no exception thrown)
3. The `Immediate` type is used but not defined in this specification (assumed to be a 4-byte integer type)
4. `MEMORY_SIZE` must be defined elsewhere in the codebase

## Dependencies
- `<cstring>` for `memset`
- `<iostream>` for debug output
- Assumes existence of `Immediate` type definition

This specification provides all necessary information to reimplement the `Memory` class while preserving its exact behavior and interface.