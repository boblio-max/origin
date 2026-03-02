# Origin Programming Language v1.7

> [!IMPORTANT]
> **ORIGIN IS TRANSITIONING TO A BYTECODE COMPILER**
> This version introduces significant architectural changes to improve execution speed and type safety through a dedicated bytecode format and Virtual Machine (VM).

## Description

Origin is a Python-based programming language with syntax designed to be closer to English. It enables AI models to produce scalable code with higher accuracy while retaining the power of traditional programming languages. Origin is highly extensible and aims to eventually support all features provided by Python.

### Features
*   **English-like syntax**: Write code that reads almost like natural language.
*   **Strict Typing**: Designed for AI-native programming. All variable declarations require explicit type annotations, ensuring predictable state and better error detection.
*   **Object-oriented design**: Built-in support for Classes, objects, inheritance, and encapsulation.
*   **Bytecode Execution**: Compiled into efficient bytecode for faster execution via the Origin VM.
*   **Extensible**: Easily add custom functions, modules, and hardware integrations.
*   **Beginner-friendly**: Simplifies complex constructs without sacrificing flexibility.

## Visit Website
[ORIGIN DOCUMENTATION](https://docs-origin.onrender.com)

## Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/boblio-max/origin.git
    ```
2. **Requirements**:
    - Python 3.x

## Usage

*   **To run the application**:
    1. Import your code into the project folder as `code.txt`.
    2. In `runnerByte.py`, ensure the code file path is set correctly.
    3. Run the compiler and VM:
    ```bash
    python ORIGIN_CODE/runnerByte.py
    ```

## Example Usage: Calculator
```origin
print "WELCOME TO THE CALCULATOR"
print "This was written in Origin code!"

# Handles inputs and type casting
# Note: x and y must be declared as float to match the cast
let x: float = float(input "Enter a number: ")
let y: float = float(input "Enter another number: ")

# Let user choose operation
let op: str = input "Enter the operation (+, -, *, /): "

print "Your result is..."
if op == "+" {
    print x + b
} 
elif op == "-" {
    print x - y
} 
elif op == "*" {
    print x * y
} 
elif op == "/" {
    print x / y
}
```

## Example Usage: Fibonacci Sequence
```origin
print "Welcome to the Fibonacci Sequence!"
let a: int = 0
let b: int = 1

let itr: int = int(input "Enter the iteration number: ")
let end: int = itr + 1

for i in range(0, end) {
    print a
    let c: int = a + b
    a = b
    b = c
}
```

## Future Improvements
*   Integrated GUI IDE for Origin.
*   Expanded support for Python libraries and dependencies.
  
## Contributing

Feel free to submit pull requests or open issues.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

*   **Email**: [nikhilmahankali56@gmail.com](mailto:nikhilmahankali56@gmail.com)
