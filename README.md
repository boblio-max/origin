# Origin Programming Lanuage

## Description

Origin is a python based programming language with syntax designed to be closer to English, letting AI models accurately produce scalable code without errors, while retaining the power of traditional programming languages. It is highly extensible and aims to eventually support ass features that Python provides.
### Features
English-like syntax: Write code that reads almost like natural language.

Object-oriented design: Classes, objects, inheritance, and encapsulation.

Efficient execution: Built on Python for fast prototyping.

Extensible: Easily add custom functions, modules, and features.

Beginner-friendly: Simplifies complex constructs without sacrificing flexibility.

## Visit Website
docs-origin.onrender.com
## Installation

**Clone the repository**:
    ```
    git clone https://github.com/boblio-max/origin.git
    ```
****
**Requirements**:
    ```
    python
    ```
## Usage

*   **To run the application**:
*   import code into folder as code.txt
*   in runner.py set code file to desired one
*   run runner.py

## Example Usage
```
print "WELCOME TO THE CALCULATOR"
print "This was written in Origin code!"

# Handles inputs and type casting
let x = float(input "Enter a number: ")
let y = float(input "Enter a number: ")

# Lets User choose input
let op = input "Enter the operation(+, -, *, /): "

#handles printing of once operation is chosen
print "Your number is..."
if op == "+" {
    print x + y
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
## OR
## Example Usage
```
print "Welcome to the fibonacci Sequence!"
let a = 0
let b = 1

let itr = int(input "Enter the iteration number: ")
let itr = itr + 1
for i in range(0, itr) {
    print a
    let c = a + b
    let a = b
    let b = c
}



## Future Improvements
*    GUI containing an origin IDE
*    support for python libraries and dependencies

  
## Contributing

Feel free to submit pull requests or open issues.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

*   **Email**: [nikhilmahankali56@gmail.com](mailto:nikhilmahankali56@gmail.com)
