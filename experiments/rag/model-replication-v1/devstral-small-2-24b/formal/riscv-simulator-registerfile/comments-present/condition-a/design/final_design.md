# RegisterFile Class Design Specification

## Overview
The `RegisterFile` class is a component that manages a set of registers in a processor-like system. It maintains two sets of register values: `prev` (previous state) and `next` (next state), allowing for pipelined or time-stepped operation.

## Class Structure

### Constants
- `REG_NUM`: Static constant defining the number of registers (32)

### Member Variables
1. **Register Arrays**:
   - `Immediate prev[REG_NUM]`: Array storing previous register values
   - `Immediate next[REG_NUM]`: Array storing next register values

### Constructor
```cpp
RegisterFile()
```
- Initializes both `prev` and `next` arrays to zero using `memset`

## Methods

### tick()
```cpp
void tick()
```
- Copies the contents of `next` array to `prev` array using `memcpy`
- Effectively advances the register state by one cycle

### read()
```cpp
Immediate read(int id)
```
- Parameters:
  - `id`: Register identifier (0-31)
- Returns:
  - 0 if `id` is 0 (special case for zero register)
  - Value from `prev[id]` otherwise
- Note: This implements the RISC-V convention where register 0 always reads as 0

### write()
```cpp
void write(int id, Immediate val)
```
- Parameters:
  - `id`: Register identifier (0-31)
  - `val`: Value to write to the register
- Effect:
  - Stores `val` in `next[id]`
  - The actual update occurs during the next tick()

### debug()
```cpp
void debug()
```
- Displays the current state of all registers in a formatted table
- Uses a predefined list of register names for display purposes
- Formats output in groups of 8 registers per row, with 4 rows total (32 registers)
- Calls `debug_immediate()` helper function to format individual register values

## Implementation Notes

1. **Register Naming**:
   - The debug method uses a predefined list of register names following RISC-V convention
   - Names include special-purpose registers (ra, sp, gp, tp) and general-purpose registers (t0-t6, s0-s11, a0-a7)

2. **Zero Register Handling**:
   - Explicitly handles register 0 to always return 0 when read
   - This follows RISC-V architecture where x0 is hardwired to zero

3. **Pipelining Support**:
   - The two-array design (prev/next) supports pipelined operation
   - Writes go to next state, reads come from previous state
   - tick() advances the pipeline stage

4. **Memory Management**:
   - Uses C-style memory operations (memset, memcpy)
   - No dynamic memory allocation in current implementation

## Dependencies
- `Immediate` type (assumed to be a numeric type for register values)
- `debug_immediate()` function (used by debug method)
- `<iostream>` and `<iomanip>` for output formatting
- `<vector>` and `<string>` for register name storage

## Design Considerations
1. The class is designed for use in a processor simulation or emulator
2. The two-array design allows for safe pipelined operation without race conditions
3. Register 0 special handling follows RISC-V architecture conventions
4. Debug output is formatted for human readability with register names

This specification provides all necessary information to reimplement the `RegisterFile` class while preserving its exact behavior and interface.