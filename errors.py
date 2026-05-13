"""errors

Custom error handling and reporting for the Origin language.
Translates Python exceptions into user-friendly Origin error reports.
"""

import sys
import linecache

def report_error(file_path, error_message, line_num=None, code_context=None):
    """Prints a beautiful, formatted error message to the console."""
    print("\n" + "="*50)
    print(" [!] ORIGIN RUNTIME ERROR")
    print("="*50)
    
    if line_num:
        print(f" Location: {file_path} (Line {line_num})")
    else:
        print(f" Location: {file_path}")
        
    print(f" Message:  {error_message}")
    print("-" * 50)
    
    # Show the code context if we have it
    if line_num:
        # If we didn't get code_context, try to read it from the file
        if not code_context and file_path and line_num > 0:
            code_context = linecache.getline(file_path, line_num).strip()
            
        if code_context:
            print(f" {line_num} | {code_context}")
            print(" " * (len(str(line_num)) + 3) + "^")
            
    print("="*50 + "\n")

def translate_python_error(exc_type, exc_value):
    """Translates common Python errors into friendly Origin messages."""
    msg = str(exc_value)
    
    if exc_type == NameError:
        var_name = msg.split("'")[1] if "'" in msg else "something"
        return f"Unknown Variable: I don't recognize '{var_name}'. Did you forget to define it with 'let'?"
    
    if exc_type == TypeError:
        if "can only concatenate str" in msg:
            return "Type Mismatch: You're trying to add a Number to a Piece of Text. Use 'str()' to convert the number first."
        if "unsupported operand type(s)" in msg:
            return "Math Error: You're trying to do math with two things that don't match (like a Number and a List)."
        return f"Type Error: {msg}"
    
    if exc_type == ZeroDivisionError:
        return "Math Error: You tried to divide by zero! Math doesn't like that."
    
    if exc_type == IndexError:
        return "Range Error: You tried to access an item that doesn't exist in that List."
    
    if exc_type == KeyError:
        return f"Key Error: I couldn't find '{msg}' in that Dictionary."

    return f"General Error: {msg}"
