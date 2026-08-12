# Register Class Design Specification

## Overview
This document provides a detailed specification for the `Register` class, which is a template-based data structure used to model a register in a processor or similar system. The class maintains two values (`prev` and `next`) representing the current and next state of the register, with stalling capability.

## Class Definition

### Template Parameter
- **T**: Arbitrary type (must support default construction and assignment)

### Public Members
1. **Data Members**:
   - `T prev`: Previous value of the register
   - `T next`: Next value to be written
   - `bool _stall`: Stall flag indicating whether writes should be blocked

2. **Methods**:
   - Constructor: Default constructor initializing both values to 0 (cast from T) and stall flag to false
   - Constructor: Parameterized constructor taking initial value for both prev and next, stall flag set to false
   - `T read()`: Returns the current value (prev)
   - `T current()`: Returns the next value (next)
   - `void write(const T &t)`: Updates the next value
   - `void tick()`: Updates prev from next if not stalled
   - `void stall(bool stall)`: Sets the stall flag
   - Conversion operator to T: Equivalent to read()
   - Assignment operator from T: Equivalent to write()

## Behavior Specification

### State Transitions
1. **Normal Operation**:
   - On tick(), prev is updated with next's value unless stalled
   - write() updates next without affecting current state until next tick

2. **Stalled Operation**:
   - When stalled, tick() does not update prev
   - write() still updates next during stall period
   - Stall can be toggled at any time via stall()

### Thread Safety
- The class is not thread-safe by default (no synchronization mechanisms)
- Concurrent access should be externally synchronized if needed

## Usage Examples

```cpp
// Basic usage
Register<int> reg;
reg.write(42);
reg.tick();  // Now read() returns 42
int value = reg;  // Uses conversion operator

// Stalling behavior
Register<float> stallReg(3.14f);
stallReg.stall(true);
stallReg.write(2.71f);  // next is updated but prev remains 3.14f
stallReg.tick();        // prev still 3.14f (no update due to stall)
stallReg.stall(false);
stallReg.tick();        // prev now updates to 2.71f
```

## Implementation Notes

1. **Type Safety**:
   - The template parameter T must support:
     - Default construction (for initialization with 0)
     - Copy assignment
     - Comparison operations if used in conditional contexts

2. **Memory Management**:
   - No dynamic memory allocation within the class
   - All members are value types (no pointers)

3. **Performance Characteristics**:
   - All operations are O(1) time complexity
   - Minimal overhead for basic register operations

## Dependencies
- None (header-only implementation)
- Standard C++ template mechanisms

This specification provides all necessary information to reimplement the Register class while preserving its exact behavior and interface.