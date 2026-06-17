import sys
import os
import traceback
import linecache
import warnings


def report_error(
    file_path,
    error_message,
    line_num=None,
    code_context=None,
    error_type="Runtime Error",
    suggestion=None
):
    print("\n" + "=" * 60)
    print(f" [!] ORIGIN {error_type.upper()}")
    print("=" * 60)

    if file_path:
        if line_num:
            print(f" Location : {file_path} (Line {line_num})")
        else:
            print(f" Location : {file_path}")
    else:
        print(" Location : <unknown>")

    print(f" Message  : {error_message}")

    if line_num:
        if not code_context and file_path and os.path.exists(file_path):
            code_context = linecache.getline(file_path, line_num).rstrip()

        print("-" * 60)

        if code_context:
            print(f" {line_num} | {code_context}")

            spacing = len(str(line_num)) + 3
            print(" " * spacing + "^")

    if suggestion:
        print("-" * 60)
        print(f" Suggestion: {suggestion}")

    print("=" * 60 + "\n")


def translate_python_error(exc_type, exc_value):
    msg = str(exc_value)

    if issubclass(exc_type, SyntaxError):
        return (
            "Syntax Error",
            f"Your code has invalid syntax. {msg}",
            "Check punctuation, parentheses, colons, and indentation."
        )

    if issubclass(exc_type, IndentationError):
        return (
            "Indentation Error",
            "Your indentation is incorrect.",
            "Make sure blocks line up properly."
        )

    if issubclass(exc_type, TabError):
        return (
            "Indentation Error",
            "You mixed tabs and spaces.",
            "Use only spaces or only tabs consistently."
        )

    if issubclass(exc_type, NameError):
        var_name = msg.split("'")[1] if "'" in msg else "something"

        return (
            "Unknown Variable",
            f"I don't recognize '{var_name}'.",
            "Did you forget to define it with 'let'?"
        )

    if issubclass(exc_type, UnboundLocalError):
        return (
            "Scope Error",
            "You tried to use a variable before assigning it.",
            "Make sure the variable is created before use."
        )

    if issubclass(exc_type, TypeError):

        if "can only concatenate str" in msg:
            return (
                "Type Mismatch",
                "You're trying to combine Text with a Number.",
                "Convert the Number using str()."
            )

        if "unsupported operand type" in msg:
            return (
                "Math Error",
                "You're using incompatible types in an operation.",
                "Check that both values are compatible."
            )

        return (
            "Type Error",
            msg,
            "Check function arguments and variable types."
        )

    if issubclass(exc_type, ValueError):
        return (
            "Value Error",
            msg,
            "One of the values is invalid for this operation."
        )

    if issubclass(exc_type, ZeroDivisionError):
        return (
            "Math Error",
            "You tried to divide by zero.",
            "A denominator cannot be zero."
        )

    if issubclass(exc_type, OverflowError):
        return (
            "Overflow Error",
            "A number became too large.",
            "Try using smaller values."
        )

    if issubclass(exc_type, FloatingPointError):
        return (
            "Floating Point Error",
            "A floating point calculation failed.",
            "Check your mathematical operations."
        )

    if issubclass(exc_type, ArithmeticError):
        return (
            "Arithmetic Error",
            msg,
            "A mathematical operation failed."
        )

    if issubclass(exc_type, IndexError):
        return (
            "Range Error",
            "You tried to access an item outside the List range.",
            "Check the index value."
        )

    if issubclass(exc_type, KeyError):
        return (
            "Key Error",
            f"The key {msg} does not exist.",
            "Check the Dictionary keys."
        )

    if issubclass(exc_type, AttributeError):
        return (
            "Attribute Error",
            msg,
            "That object does not contain the requested property or method."
        )

    if issubclass(exc_type, ImportError):
        return (
            "Import Error",
            msg,
            "A required module could not be imported."
        )

    if issubclass(exc_type, ModuleNotFoundError):
        return (
            "Module Error",
            msg,
            "The requested module does not exist."
        )

    if issubclass(exc_type, FileNotFoundError):
        return (
            "File Error",
            "The requested file could not be found.",
            "Check the file path and filename."
        )

    if issubclass(exc_type, PermissionError):
        return (
            "Permission Error",
            "You do not have permission to access this file.",
            "Check file permissions."
        )

    if issubclass(exc_type, IsADirectoryError):
        return (
            "File Error",
            "Expected a file but got a directory.",
            "Provide a valid file."
        )

    if issubclass(exc_type, NotADirectoryError):
        return (
            "Directory Error",
            "Expected a directory but got a file.",
            "Provide a valid directory."
        )

    if issubclass(exc_type, OSError):
        return (
            "System Error",
            msg,
            "An operating system error occurred."
        )

    if issubclass(exc_type, RuntimeError):
        return (
            "Runtime Error",
            msg,
            "Something unexpected happened during execution."
        )

    if issubclass(exc_type, RecursionError):
        return (
            "Recursion Error",
            "Maximum recursion depth exceeded.",
            "Your function may be calling itself forever."
        )

    if issubclass(exc_type, NotImplementedError):
        return (
            "Not Implemented",
            "This feature has not been implemented yet.",
            "Try another approach."
        )

    if issubclass(exc_type, MemoryError):
        return (
            "Memory Error",
            "The program ran out of memory.",
            "Reduce memory usage or input size."
        )

    if issubclass(exc_type, UnicodeError):
        return (
            "Unicode Error",
            msg,
            "There was a text encoding issue."
        )

    if issubclass(exc_type, TimeoutError):
        return (
            "Timeout Error",
            "The operation took too long.",
            "Try again or optimize the operation."
        )

    if issubclass(exc_type, EOFError):
        return (
            "Input Error",
            "Unexpected end of input.",
            "Input may be incomplete."
        )

    if issubclass(exc_type, KeyboardInterrupt):
        return (
            "Interrupted",
            "Execution was interrupted by the user.",
            None
        )

    if issubclass(exc_type, AssertionError):
        return (
            "Assertion Failed",
            msg if msg else "An assertion failed.",
            "Check the expected conditions."
        )

    if issubclass(exc_type, ReferenceError):
        return (
            "Reference Error",
            msg,
            "An invalid object reference was used."
        )

    if issubclass(exc_type, BufferError):
        return (
            "Buffer Error",
            msg,
            "A buffer-related operation failed."
        )

    if issubclass(exc_type, ConnectionError):
        return (
            "Connection Error",
            msg,
            "A network-related error occurred."
        )

    if issubclass(exc_type, StopIteration):
        return (
            "Iteration Complete",
            "The iterator has no more items.",
            None
        )

    if issubclass(exc_type, StopAsyncIteration):
        return (
            "Async Iteration Complete",
            "The async iterator has no more items.",
            None
        )

    if issubclass(exc_type, Warning):
        return (
            "Warning",
            msg,
            None
        )

    return (
        exc_type.__name__,
        msg,
        "An unknown error occurred."
    )


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        print("\n[!] Execution interrupted.")
        return

    tb = traceback.extract_tb(exc_traceback)

    if tb:
        last = tb[-1]
        file_path = last.filename
        line_num = last.lineno
        code_context = last.line
    else:
        file_path = "<unknown>"
        line_num = None
        code_context = None

    error_type, friendly_message, suggestion = translate_python_error(
        exc_type,
        exc_value
    )

    report_error(
        file_path=file_path,
        error_message=friendly_message,
        line_num=line_num,
        code_context=code_context,
        error_type=error_type,
        suggestion=suggestion
    )


def handle_warning(message, category, filename, lineno, file=None, line=None):
    report_error(
        file_path=filename,
        error_message=str(message),
        line_num=lineno,
        code_context=line,
        error_type="Warning"
    )


def install():
    sys.excepthook = handle_exception
    warnings.showwarning = handle_warning