# RegisterFile Class Design Specification

## Overview
The `RegisterFile` class is a component of a processor's register file implementation, managing 32 registers with support for pipelining through previous and next state tracking.

## Class Structure

### Constants
- `REG_NUM`: Static constant set to 32 (number of registers)

### Member Variables
1. **prev[REG_NUM]**: Array storing the previous state of each register
   - Type: `Immediate` (opaque type)
   - Purpose: Tracks register values from the previous clock cycle

2. **next[REG_NUM]**: Array storing the next state of each register
   - Type: `Immediate` (opaque type)
   - Purpose: Stores pending writes that will take effect on the next clock cycle

### Constructor
- Initializes both `prev` and `next` arrays to zero using `memset`

## Methods

### tick()
- **Purpose**: Advances the pipeline stage by copying next state to previous state
- **Implementation**:
  ```cpp
  void tick() { memcpy(prev, next, sizeof(prev)); }
  ```

### read(int id)
- **Purpose**: Reads a register value
- **Parameters**:
  - `id`: Register identifier (0-31)
- **Returns**:
  - For register 0: Returns 0 (hardwired zero register)
  - For other registers: Returns the previous state value
- **Implementation**:
  ```cpp
  Immediate read(int id) { return id == 0 ? 0 : prev[id]; }
  ```

### write(int id, Immediate val)
- **Purpose**: Writes a value to a register (to be effective on next cycle)
- **Parameters**:
  - `id`: Register identifier (0-31)
  - `val`: Value to write
- **Implementation**:
  ```cpp
  void write(int id, Immediate val) { next[id] = val; }
  ```

### debug()
- **Purpose**: Prints the current state of all registers in a formatted table
- **Implementation Details**:
  1. Uses a static vector `rf_name` containing register names:
     - Index 0: "0" (hardwired zero)
     - Indices 1-31: Standard RISC-V register names ("ra", "sp", "gp", etc.)
  2. Prints registers in groups of 8, organized into 4 rows
  3. For each register:
     - Prints identifier (e.g., "#0") and name (left-aligned)
     - Calls `debug_immediate()` to print the value (right-aligned)
  4. Uses `std::setw` for formatting

## Design Considerations

1. **Pipelining Support**:
   - The class implements a two-stage pipeline with separate arrays for previous and next states
   - The `tick()` method handles state advancement between stages

2. **Hardwired Zero Register**:
   - Register 0 always returns 0, regardless of written values

3. **Debugging Interface**:
   - Provides formatted output showing all register contents
   - Uses external `debug_immediate()` function for value formatting

4. **Memory Management**:
   - Arrays are fixed-size (32 elements) and stack-allocated
   - No dynamic memory allocation required

## External Dependencies

1. **Immediate Type**: Opaque type used for register values
2. **debug_immediate()**: External function for printing Immediate values
3. **Standard Library Components**:
   - `<vector>` for register names storage
   - `<iostream>` and `<iomanip>` for debug output formatting

## Implementation Notes

1. The class does not handle register file hazards or forwarding logic
2. All register writes are committed on the next clock cycle (tick)
3. The debug output format is fixed with 4 rows of 8 registers each
4. Register names follow RISC-V convention but are hardcoded in the implementation

This specification provides all necessary information for a complete reimplementation while preserving the original structure and behavior.