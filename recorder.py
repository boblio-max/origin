import json
import os

class Recorder:
    def __init__(self):
        self.history = []
        self.current_logs = []

    def reset(self):
        self.history = []
        self.current_logs = []

    def log(self, *args):
        message = " ".join(map(str, args))
        self.current_logs.append(message)
        print(message)

    def record(self, variables, line):
        # Filter out internal variables and the recorder itself
        # Also filter out common runner-specific noise
        excluded = {
            "lex", "Parser", "interpreter", "parallelInt", "os", "sys", "time", 
            "code_lines", "name", "find_or_files", "folder", "files", "out", 
            "path", "header", "f", "content", "code_name", "file", "start_time", 
            "tokens", "parser", "ast", "par_ast", "origin", "origin_code", "last_idx", "nl_idx",
            "line"
        }
        filtered_vars = {}
        for k, v in variables.items():
            if k.startswith("_") or k == "_recorder" or k in excluded:
                continue
            # Try to store only serializable values
            try:
                # Check if it's JSON serializable
                json.dumps(v)
                filtered_vars[k] = v
            except (TypeError, OverflowError):
                filtered_vars[k] = str(v)
        
        snapshot = {
            "line": line,
            "variables": filtered_vars,
            "logs": list(self.current_logs)
        }
        self.history.append(snapshot)

    def export_history(self, filename="history.json"):
        with open(filename, "w") as f:
            json.dump(self.history, f, indent=2)
        print(f"\n[Recorder] History exported to {filename}")

# Global instance
_instance = Recorder()

def reset():
    _instance.reset()

def log(*args):
    _instance.log(*args)

def record(variables, line):
    _instance.record(variables, line)

def export_history(filename="history.json"):
    _instance.export_history(filename)
