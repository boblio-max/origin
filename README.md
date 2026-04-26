# Origin Programming Language · v1.7.5

[![Status](https://img.shields.io/badge/Status-Stable-success?style=flat-square)](https://docs-origin.onrender.com)
[![Version](https://img.shields.io/badge/Version-v1.7.5-blue?style=flat-square)](https://docs-origin.onrender.com)
[![Platform](https://img.shields.io/badge/Platform-Raspberry_Pi-red?style=flat-square)](https://docs-origin.onrender.com)

**Origin** is a Python-based programming language with a syntax designed to be expressive, English-like, and hardware-first. It enables AI models and developers to produce scalable code with high readability while retaining the full power of the Python ecosystem.

> [!TIP]
> **Visit the official documentation:** [docs-origin.onrender.com](https://docs-origin.onrender.com)

---

## Key Features

*   **English-Like Syntax**: Write code that reads like natural language.
*   **Hardware-First**: Native, intuitive commands for **Raspberry Pi GPIO** and **ServoKit (PCA9685)**.
*   **Strict Typing**: Mandatory type annotations (`let x: int = 10`) for predictable state and AI-native safety.
*   **Safe Hardware I/O**: Automatic angle clamping (0–180°) for servos to prevent physical damage.
*   **Full Interoperability**: Embed raw Python blocks directly within Origin scripts.
*   **Modern Logic**: Support for Object-Oriented Programming (classes), `try/except/else`, `parallel` thread blocks, and a robust module inclusion system.

---

## Installation

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/boblio-max/origin.git
   ```

2. **Install Dependencies**:
   Origin requires Python 3.x and a few hardware libraries if you are running on a Raspberry Pi:
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

### 2. Hardware Control
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

### 3. Data Structures
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

### 4. Raw Python Blocks
Seamlessly bridge the gap between Origin and Python.

```origin
py {
    import math
    import os
    print("Python process ID:", os.getpid())
    print("Sine of 90 degrees:", math.sin(math.pi/2))
}
```

### 5. Module System
Origin uses a "header-style" inclusion system.

```origin
import robotics_utils        # Prepends robotics_utils.or to current file
from math import sqrt        # Import directly from Python libraries

let val: float = sqrt(144)
```

### 6. Object-Oriented Programming
Define classes with fields and methods natively for structured development.

```origin
class Sensor (pin type) {
    def read() {
        return pin
    }
}
```

---

## Usage

Origin scripts use the `.or` (or `.txt`) extension. To translate and execute a script:

1. Place your code in a file (e.g., `main.or`).
2. Run the runner script:
   ```powershell
   python runner.py main.or
   ```

The `runner.py` will use the `interpreter.py` to translate your Origin code into Python and execute it immediately.

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
