# Origin Programming Language · v1.7.9

[![Status](https://img.shields.io/badge/Status-Stable-success?style=flat-square)](https://docs-origin.onrender.com)
[![Version](https://img.shields.io/badge/Version-v1.7.9-blue?style=flat-square)](https://docs-origin.onrender.com)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue?style=flat-square)](https://docs-origin.onrender.com)

**Origin** is a Python-based programming language with a syntax designed to be expressive, English-like, and hardware-first. It enables AI models and developers to produce scalable code with high readability while retaining the full power of the Python ecosystem.

> **Visit the official documentation:** [docs-origin.onrender.com](https://docs-origin.onrender.com)

---

## Key Features

*   **English-Like Syntax**: Write code that reads like natural language.
*   **Built-in Library System**: Import `.or` library files with `import calc`, including a math library (`calc.or`) and graph plotting library (`graph.or`).
*   **Hardware Primitives**: Native, intuitive commands for Raspberry Pi GPIO and ServoKit (PCA9685).
*   **Strict Typing**: Mandatory type annotations (`let x: int = 10`) for predictable state and AI-native safety.
*   **Safe Hardware I/O**: Automatic angle clamping (0-180 degrees) for servos to prevent physical damage.
*   **Formal Module System**: Professional namespacing and module support (`import math as m`, `from lib import x`).
*   **Binary Builder**: Compile your Origin scripts into standalone, zero-dependency `.exe` files.
*   **Modern Logic**: Support for Object-Oriented Programming (classes), `try/except/else`, `parallel` thread blocks, and robust scope management.

---

## Installation

### Standalone (Recommended)
You can now download Origin as a standalone installer for Windows. This is the fastest way to get started.

1. **Download**: [Origin v1.7.9 Stable](https://docs-origin.onrender.com/download.html)
2. **Install**: Run `secure_install.ps1` with PowerShell.
3. **Usage**: Open a new terminal and type `origin`.

### Developer / Source
1. **Clone the repository**:
   ```powershell
   git clone https://github.com/boblio-max/origin.git
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

---

## Language Reference

### 1. Variables & Types
Origin uses `let` for variables and `const` for immutable references. Types are mandatory.

```origin
let   x: int    = 10          # Scalar integer
let   name: str = "Origin"    # String literal
let   flag: bool = true       # Boolean (lowercase)
const pi: float = 3.14159     # Immutable constant
let   data: none = none       # None literal
```

### 2. Built-in Libraries
Origin includes a standard library system under `lib/`. Use `import` to load them:

```origin
import calc
import graph

# Math utilities
calc = calc()
print calc.sqrt(25)
print calc.pi

# Graph plotting
graph "My Plot" with {
    X: color(1,0,0) as "Line A",
}
```

### 3. Hardware Control
Control hardware directly with the `set` namespace and native protocol primitives.

```origin
# Set Servo 1 to 90 degrees (clamped 0-180)
set servo.angle 1, 90

# Drive BCM Pin 12 HIGH
set pin 12, 1

# Parentheseless I2C, SPI, and UART calls
i2c.read 0x40, 4
spi.write 0x01
```

### 4. Data Structures
```origin
# Lists
let tools: list = ["Servo", "GPIO", "I2C"]
print tools[0]

# Dictionaries (Access via { })
let config: dict = {"speed": 100, "active": true}
print config{"speed"}

# Tuples
let coord: tuple = (10, 20)
```

### 5. Raw Python Blocks
Seamlessly bridge the gap between Origin and Python.

```origin
py {
    import math
    import os
    print("Python process ID:", os.getpid())
    print("Sine of 90 degrees:", math.sin(math.pi/2))
}
```

### 6. Module System
Origin supports a formal module system for clean namespacing.

```origin
import math_utils as mu        # Import with alias
from robotics import drive     # Selective import

print mu.square(10)
drive(1.0)
```

### 7. Object-Oriented Programming
Define classes with fields and methods natively for structured development.

```origin
class Sensor (pin type) {
    def read() {
        return pin
    }
}
```

---

Origin scripts use the `.or` extension.

### Running a script:
```powershell
origin main.or
```

### Building a standalone binary:
```powershell
origin build main.or
```

---

## Roadmap

The following features are currently in development:
- [ ] **Pattern Matching**: `match` and `case` constructs.
- [ ] **Advanced Structures**: `struct` and `enum` types.
- [ ] **Asynchronous I/O**: Native `async` and `await` support.
- [ ] **Metaprogramming**: `macro` and `inline` definitions.
- [ ] **Unified IDE**: A dedicated cross-platform IDE for Origin development.

---

## License & Contact

Distributed under the **MIT License**.
**Author**: Nikhil Mahankali
**Contact**: [nikhilmahankali56@gmail.com](mailto:nikhilmahankali56@gmail.com)
