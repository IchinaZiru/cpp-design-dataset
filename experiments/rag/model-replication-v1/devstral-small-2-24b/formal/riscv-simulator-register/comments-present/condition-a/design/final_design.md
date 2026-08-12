# Register Class Design Specification

## Overview
This document specifies the design of the `Register` class, a template-based data structure that models a register in a computational system. The class provides basic read/write operations and supports stalling behavior.

## Class Definition
```cpp
template <typename T>
class Register {
public:
    // Data members
    T prev;      // Previous value (output of the register)
    T next;      // Next value (input to be written)
    bool _stall; // Stall flag

    // Constructors
    Register();                          // Default constructor
    Register(T d);                       // Parameterized constructor

    // Member functions
    T read() const;                      // Read current output
    T current() const;                   // Get next value (input)
    void write(const T &t);              // Write new input value
    void tick();                         // Update register state
    void stall(bool stall);               // Control stalling

    // Operators
    operator T() const;                  // Conversion to T
    void operator=(T next);              // Assignment from T
};
```

## Detailed Specification

### Template Parameter
- `T`: Arbitrary data type that the register will store. Must be copyable.

### Data Members
1. **prev (T)**
   - Stores the current output value of the register
   - Initialized to 0 in default constructor, or to parameter d in parameterized constructor

2. **next (T)**
   - Stores the next input value to be written
   - Initialized to same value as prev in both constructors

3. **_stall (bool)**
   - Controls whether the register updates on tick()
   - Initialized to false in all constructors

### Member Functions

1. **Register()**
   - Default constructor
   - Initializes prev and next to 0 (cast from T)
   - Sets _stall to false

2. **Register(T d)**
   - Parameterized constructor
   - Initializes both prev and next to parameter d
   - Sets _stall to false

3. **T read() const**
   - Returns the current output value (prev)
   - Const member function

4. **T current() const**
   - Returns the next input value (next)
   - Const member function

5. **void write(const T &t)**
   - Updates the next value to t
   - Does not affect prev until tick() is called

6. **void tick()**
   - If not stalled (_stall == false), updates prev to match next
   - If stalled, no update occurs

7. **void stall(bool stall)**
   - Sets the _stall flag to the given value
   - When true, prevents updates during tick()
   - When false, allows normal operation

### Operators

1. **operator T() const**
   - Conversion operator to type T
   - Equivalent to read()

2. **void operator=(T next)**
   - Assignment operator from type T
   - Equivalent to write(next)

## Behavior Specifications

1. **Normal Operation Flow**:
   ```
   1. write(new_value) → updates next
   2. tick()           → if not stalled, updates prev to match next
   3. read()           → returns current prev value
   ```

2. **Stall Behavior**:
   - When stalled (_stall == true), tick() has no effect on prev
   - write() still updates next while stalled
   - stall(false) resumes normal operation

## Constraints and Assumptions

1. The class is not derived from any base class (commented-out inheritance to Tickable is not implemented)
2. No virtual functions are present in this implementation
3. The template parameter T must support:
   - Default construction (for 0 initialization)
   - Copy construction/assignment
   - Comparison with 0 (for default initialization)

## Example Usage

```cpp
Register<int> reg;
reg.write(42);       // next = 42, prev unchanged
reg.tick();          // prev = 42
int value = reg.read(); // returns 42

// With stalling
reg.stall(true);
reg.write(100);      // next = 100, but won't update until unstalled
reg.tick();          // no change to prev (still 42)
reg.stall(false);
reg.tick();          // now prev updates to 100
```

## Implementation Notes

1. The class maintains a two-phase update mechanism:
   - write() updates the "next" value immediately
   - tick() propagates the next value to prev (if not stalled)

2. This design pattern is common in hardware modeling where registers have separate input and output phases.

3. The stall mechanism allows modeling of pipeline hazards or synchronization points in computational systems.

This specification provides all necessary information for a complete reimplementation of the Register class while preserving all original functionality and interface characteristics.