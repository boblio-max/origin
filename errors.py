"""
Custom error handling and reporting for the Origin language.
Translates Python exceptions into user-friendly Origin error reports.
"""

import sys
import linecache
def track_error(exc_type, exc_value, exc_traceback):
    """Tracks the error and prints a user-friendly message."""
    # Get the line number from the traceback
    line_num = exc_traceback.tb_lineno if exc_traceback else None
    
    # Get the file name from the traceback
    file_name = exc_traceback.tb_frame.f_code.co_filename if exc_traceback else None
    
    # Translate the error message
    friendly_msg = translate_python_error(exc_type, exc_value)
    
    # Report the error beautifully
    report_error(file_name, friendly_msg, line_num)

    with open("errors_log.csv", "a") as f:
        f.write("" + "="*50 + "\n")
        f.write(f"Error Type: {exc_type.__name__}\n")
        f.write(f"Error Message: {exc_value}\n")
        f.write(f"File: {file_name}\n")
        f.write(f"Line: {line_num}\n")
        f.write("="*50 + "\n\n")

def report_error(file_path, error_message, line_num=None, code_context=None):
    """Prints a beautiful, formatted error message to the console."""
    print("\n" + "="*50)
    print(" [!] Origin Error Detected [!]")
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
    
    # Already handled cases
    if exc_type == NameError:
        var_name = msg.split("'")[1] if "'" in msg else "something"
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Unknown Variable: I don't recognize '{var_name}'. Did you forget to define it with 'let'?"

    if exc_type == AssertionError:
        var = msg.split("'")[1] if "'" in msg else "something"
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Assertion Error: An assertion failed for '{var}'. Check your conditions!"
    
    if exc_type == SyntaxError:
        var = msg.split("'")[1] if "'" in msg else "something"
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Syntax Error: There's something wrong with how you wrote '{var}'. Check your syntax."

    if exc_type == TypeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        if "can only concatenate str" in msg:
            return "Type Mismatch: You're trying to add a Number to a Piece of Text. Use 'str()' to convert the number first."
        if "unsupported operand type(s)" in msg:
            return "Math Error: You're trying to do math with two things that don't match (like a Number and a List)."
        return f"Type Error: {msg}"
    
    if exc_type == ZeroDivisionError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Math Error: You tried to divide by zero! Math doesn't like that."
    
    if exc_type == IndexError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Range Error: You tried to access an item that doesn't exist in that List."
    
    if exc_type == KeyError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Key Error: I couldn't find '{msg}' in that Dictionary."

    # ==================== ALL OTHER PYTHON EXCEPTIONS ====================
    
    # AttributeError - accessing non-existent attribute/method
    if exc_type == AttributeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        attr_name = msg.split("'")[1] if "'" in msg else msg.split()[0]
        return f"Attribute Error: '{attr_name}' doesn't exist on that object. Did you mean to use something else?"
    
    # BufferError - buffer-related operations
    if exc_type == BufferError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Buffer Error: Something went wrong with a buffer operation. {msg}"
    
    # EOFError - unexpected end of file
    if exc_type == EOFError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "End of File Error: The program expected more data but reached the end unexpectedly. Did you forget to close a bracket or quote?"
    
    # ImportError / ModuleNotFoundError
    if exc_type == ImportError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        module_name = msg.split("'")[1] if "'" in msg else msg.split()[0]
        return f"Import Error: I can't find the module '{module_name}'. Did you spell it right? Is it installed?"
    
    if exc_type == ModuleNotFoundError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        module_name = msg.split("'")[1] if "'" in msg else msg.split()[0]
        return f"Module Not Found: The module '{module_name}' doesn't exist. Did you forget to import it?"
    
    # LookupError (parent of IndexError and KeyError)
    if exc_type == LookupError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Lookup Error: I couldn't find what you're looking for. {msg}"
    
    # MemoryError - out of memory
    if exc_type == MemoryError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Memory Error: Your program ran out of memory! Try using smaller data or breaking it into smaller pieces."
    
    # OSError and all its subclasses
    if exc_type == OSError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"System Error: Something went wrong with the system. {msg}"
    
    if exc_type == FileNotFoundError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        filename = msg.split("'")[1] if "'" in msg else msg.split()[0]
        return f"File Not Found: I can't find the file '{filename}'. Check the path and make sure it exists."
    
    if exc_type == FileExistsError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        filename = msg.split("'")[1] if "'" in msg else msg.split()[0]
        return f"File Exists Error: The file '{filename}' already exists. Use a different name or delete it first."
    
    if exc_type == PermissionError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Permission Error: You don't have permission to do that. Try running with the right permissions."
    
    if exc_type == IsADirectoryError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Directory Error: You tried to use a directory (folder) like a file. That's not allowed!"
    
    if exc_type == NotADirectoryError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Not a Directory Error: You tried to use something that's not a folder as if it were a folder."
    
    if exc_type == ConnectionError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Connection Error: I couldn't connect to what you're trying to reach. Check your connection!"
    
    if exc_type == ConnectionRefusedError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Connection Refused: The connection was actively refused. Is the server running?"
    
    if exc_type == ConnectionResetError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Connection Reset: The connection was reset. Something went wrong with the network."
    
    if exc_type == ConnectionAbortedError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Connection Aborted: The connection was aborted. The operation was cancelled."
    
    if exc_type == BrokenPipeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Broken Pipe Error: The connection was broken. The other end stopped listening."
    
    if exc_type == TimeoutError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Timeout Error: The operation took too long and timed out. Try again or check if it's stuck."
    
    if exc_type == ProcessLookupError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Process Error: I couldn't find that process. It might not be running."
    
    if exc_type == InterruptedError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Interrupted Error: The operation was interrupted. Maybe you pressed Ctrl+C?"
    
    if exc_type == ChildProcessError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Child Process Error: Something went wrong with a child process. {msg}"
    
    if exc_type == BlockingIOError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Blocking IO Error: The operation would block. Try a different approach."
    
    # ArithmeticError and subclasses
    if exc_type == ArithmeticError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Arithmetic Error: Something went wrong with a math operation. {msg}"
    
    if exc_type == FloatingPointError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Floating Point Error: Something went wrong with a decimal number calculation."
    
    if exc_type == OverflowError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Overflow Error: The number got too big to handle! Try using smaller numbers."
    
    # ReferenceError
    if exc_type == ReferenceError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Reference Error: There's a problem with a reference. {msg}"
    
    # RuntimeError and subclasses
    if exc_type == RuntimeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Runtime Error: Something went wrong while the program was running. {msg}"
    
    if exc_type == NotImplementedError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Not Implemented Error: This feature hasn't been built yet. It's coming soon!"
    
    if exc_type == RecursionError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Recursion Error: The function called itself too many times! Check for infinite recursion."
    
    # StopIteration
    if exc_type == StopIteration:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Stop Iteration: The iterator has no more items. The loop should have stopped."
    
    # StopAsyncIteration
    if exc_type == StopAsyncIteration:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Stop Async Iteration: The async iterator has no more items."
    
    # IndentationError and TabError
    if exc_type == IndentationError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Indentation Error: Your code isn't indented properly. Check your spacing!"
    
    if exc_type == TabError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Tab Error: You mixed tabs and spaces. Pick one and stick with it!"
    
    # UnicodeError and subclasses
    if exc_type == UnicodeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Unicode Error: There's a problem with text encoding. {msg}"
    
    if exc_type == UnicodeDecodeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Unicode Decode Error: I couldn't decode that text. Check the encoding!"
    
    if exc_type == UnicodeEncodeError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Unicode Encode Error: I couldn't encode that text. Check the characters!"
    
    if exc_type == UnicodeTranslateError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Unicode Translate Error: Something went wrong translating that text."
    
    # ValueError
    if exc_type == ValueError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Value Error: The value is not valid. {msg}"
    
    # SystemError
    if exc_type == SystemError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"System Error: There's an internal system error. {msg}"
    
    # GeneratorExit
    if exc_type == GeneratorExit:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Generator Exit: The generator was closed before it finished."
    
    # KeyboardInterrupt (Ctrl+C)
    if exc_type == KeyboardInterrupt:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Interrupted: You stopped the program (Ctrl+C). Goodbye!"
    
    # SystemExit (sys.exit())
    if exc_type == SystemExit:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Program Exit: The program exited. See you later!"
    
    # TabError (duplicate, but keeping for completeness)
    if exc_type == TabError:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return "Tab Error: Inconsistent use of tabs and spaces in indentation."
    
    # Warning (not an Exception, but sometimes raised)
    if exc_type == Warning:
        track_error(exc_type, exc_value, sys.exc_info()[2])
        return f"Warning: {msg}"
    
    # Exception (catch-all)
    track_error(exc_type, exc_value, sys.exc_info()[2])
    return f"Unexpected Error ({exc_type.__name__}): {msg}"