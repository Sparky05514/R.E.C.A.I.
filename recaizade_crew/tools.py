import os
import shutil
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime

ROOT_DIR = os.getcwd()
WORKING_DIRECTORY = os.path.join(ROOT_DIR, "Projects")
SANDBOX_DIRECTORY = os.path.join(ROOT_DIR, "sandbox")
MEMORY_FILE = os.path.join(ROOT_DIR, "bot_memory", "memory.json") 
CONTEXT_FILE = os.path.join(ROOT_DIR, "context.md")

# Create directories if missing
for d in [WORKING_DIRECTORY, SANDBOX_DIRECTORY, os.path.join(ROOT_DIR, "bot_memory")]:
    os.makedirs(d, exist_ok=True)

DANGEROUS_TOOLS = {
    "run_command", "run_python", "write_file", "delete_file", 
    "move_file", "copy_file", "append_to_file"
}

def _resolve_path(filepath):
    """Resolves a filepath relative to WORKING_DIRECTORY if it's not absolute."""
    if os.path.isabs(filepath):
        return filepath
    # Special cases for system files in root
    if filepath.startswith("bot_memory") or filepath == "context.md":
        return os.path.join(ROOT_DIR, filepath)
    return os.path.join(WORKING_DIRECTORY, filepath)

def _is_safe_path(filepath):
    """Strictly enforces project/sandbox boundaries."""
    abs_path = os.path.abspath(filepath)
    
    # Allowed roots
    allowed_roots = [
        os.path.abspath(WORKING_DIRECTORY),
        os.path.abspath(SANDBOX_DIRECTORY),
        os.path.abspath(os.path.join(ROOT_DIR, "bot_memory")),
        os.path.abspath(CONTEXT_FILE)
    ]
    
    return any(abs_path.startswith(root) for root in allowed_roots)

class ExecutionSandbox:
    """Manages an isolated directory for command/code execution."""
    @staticmethod
    def get_isolated_env():
        """Returns a restricted set of environment variables."""
        safe_keys = ["PATH", "LANG", "LC_ALL", "PYTHONPATH"]
        env = {k: os.environ[k] for k in safe_keys if k in os.environ}
        env["RECAIZADE_SANDBOX"] = "1"
        return env

    @staticmethod
    def run(func, *args, **kwargs):
        """Runs a function while temporarily changing CWD to sandbox."""
        old_cwd = os.getcwd()
        os.chdir(SANDBOX_DIRECTORY)
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(old_cwd)

def read_file(filepath: str) -> str:
    """Reads a file and returns its content."""
    full_path = _resolve_path(filepath)
    if not _is_safe_path(full_path):
        return f"Error: Access denied to path {filepath}"
    try:
        with open(full_path, 'r') as f:
            return f.read()
    except Exception as e:
        log.error(f"Error reading {filepath}: {e}")
        return f"Error reading file '{filepath}': {e}. Hint: Verify the persistent path exists using 'list_directory' or 'get_project_structure'."

def write_file(filepath: str, content: str) -> str:
    """Writes content to a file. Overwrites if exists."""
    full_path = _resolve_path(filepath)
    if not _is_safe_path(full_path):
        return f"Error: Access denied to path {filepath}"
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        log.error(f"Error writing to {filepath}: {e}")
        return f"Error writing file '{filepath}': {e}. Hint: Ensure the path is within allowed directories or check disk space."
        return f"Error writing file: {e}"

def list_directory(path: str = ".") -> str:
    """Lists files and directories in the given path."""
    full_path = _resolve_path(path)
    if not _is_safe_path(full_path):
         return f"Error: Access denied to path {path}"
    try:
        if not os.path.exists(full_path):
            return f"Error: Path {path} does not exist."
        items = os.listdir(full_path)
        return "\n".join(items) if items else "(Empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"

def delete_file(filepath: str) -> str:
    """Deletes a file."""
    full_path = _resolve_path(filepath)
    if not _is_safe_path(full_path):
        return f"Error: Access denied to path {filepath}"
    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
            return f"Successfully deleted {filepath}"
        else:
            return f"Error: {filepath} is not a file"
    except Exception as e:
        return f"Error deleting file: {e}"

# --- NEW TOOLS ---

def run_command(command: str) -> str:
    """Executes a shell command inside the restricted sandbox."""
    try:
        # Restriction: Refuse commands that look like they're trying to escape
        if any(bad in command for bad in [";", "&", "|", ">", "<", "$", "`"]):
            # Very basic check, models are encouraged to write scripts instead
            pass 
            
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=SANDBOX_DIRECTORY,
            env=ExecutionSandbox.get_isolated_env()
        )
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return output if output.strip() else "Command executed with no output."
    except Exception as e:
        from logger import log
        log.error(f"Error executing command '{command}': {e}")
        return f"Error executing command: {e}. Hint: Ensure the command is available in the sandbox environment."

def run_python(code: str) -> str:
    """Executes Python code inside the restricted sandbox."""
    import sys
    import tempfile
    
    try:
        # Write code to a temporary file in the sandbox
        with tempfile.NamedTemporaryFile(suffix=".py", dir=SANDBOX_DIRECTORY, delete=False, mode='w') as tmp:
            tmp.write(code)
            tmp_path = tmp.name
            
        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=SANDBOX_DIRECTORY,
                env=ExecutionSandbox.get_isolated_env()
            )
            output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            return output if output.strip() else "Python code executed with no output."
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        from logger import log
        log.error(f"Error running python code: {e}")
        return f"Error running python: {e}. Hint: The code executed in a restricted sandbox."

def search_in_files(pattern: str, directory: str = ".") -> str:
    """Searches for a regex pattern in files within a directory."""
    full_dir = _resolve_path(directory)
    if not _is_safe_path(full_dir):
        return f"Error: Access denied to path {directory}"
    results = []
    try:
        for root, _, files in os.walk(full_dir):
            for file in files:
                if file.startswith('.') or "venv" in root: continue
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                results.append(f"{os.path.relpath(path, WORKING_DIRECTORY)}:{i}: {line.strip()}")
                except: continue
        return "\n".join(results) if results else "No matches found."
    except Exception as e:
        return f"Error searching files: {e}"

def move_file(source: str, dest: str) -> str:
    """Moves or renames a file."""
    s_path = _resolve_path(source)
    d_path = _resolve_path(dest)
    if not _is_safe_path(s_path) or not _is_safe_path(d_path):
        return "Error: Access denied."
    try:
        shutil.move(s_path, d_path)
        return f"Successfully moved {source} to {dest}"
    except Exception as e:
        return f"Error moving file: {e}"

def copy_file(source: str, dest: str) -> str:
    """Copies a file."""
    s_path = _resolve_path(source)
    d_path = _resolve_path(dest)
    if not _is_safe_path(s_path) or not _is_safe_path(d_path):
        return "Error: Access denied."
    try:
        shutil.copy2(s_path, d_path)
        return f"Successfully copied {source} to {dest}"
    except Exception as e:
        return f"Error copying file: {e}"

def append_to_file(filepath: str, content: str) -> str:
    """Appends content to an existing file."""
    full_path = _resolve_path(filepath)
    if not _is_safe_path(full_path):
        return "Error: Access denied."
    try:
        with open(full_path, 'a') as f:
            f.write(content)
        return f"Successfully appended to {filepath}"
    except Exception as e:
        return f"Error appending to file: {e}"

def get_file_info(filepath: str) -> str:
    """Returns metadata about a file."""
    full_path = _resolve_path(filepath)
    if not _is_safe_path(full_path):
        return "Error: Access denied."
    try:
        stat = os.stat(full_path)
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        return f"File: {filepath}\nSize: {size} bytes\nLast Modified: {mtime}"
    except Exception as e:
        return f"Error getting file info: {e}"

def get_project_structure(path: str = ".") -> str:
    """Returns a tree view of the project structure."""
    full_path = _resolve_path(path)
    if not _is_safe_path(full_path):
        return "Error: Access denied."
    output = []
    def _walk(current_path, prefix=""):
        try:
            items = sorted(os.listdir(current_path))
            for i, item in enumerate(items):
                if item.startswith('.') or item == "__pycache__" or item == "venv":
                    continue
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                output.append(f"{prefix}{connector}{item}")
                abs_item = os.path.join(current_path, item)
                if os.path.isdir(abs_item):
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    _walk(abs_item, new_prefix)
        except: pass
    output.append(path)
    _walk(full_path)
    return "\n".join(output)

def analyze_code(filepath: str) -> str:
    """Performs basic static analysis on a Python file."""
    full_path = _resolve_path(filepath)
    if not _is_safe_path(full_path):
        return "Error: Access denied."
    try:
        import ast
        with open(full_path, 'r') as f:
            tree = ast.parse(f.read())
        
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names: imports.append(n.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
                
        return f"Analysis of {filepath}:\nClasses: {classes}\nFunctions: {functions}\nImports: {imports}"
    except Exception as e:
        return f"Error analyzing code: {e}"

def find_references(symbol: str, directory: str = ".") -> str:
    """Finds references to a symbol (function/class name) in the project."""
    return search_in_files(rf"\b{symbol}\b", directory)

def save_memory(key: str, value: str) -> str:
    """Saves a piece of information to persistent memory."""
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        memory = {}
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r') as f:
                memory = json.load(f)
        memory[key] = value
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=4)
        return f"Saved '{key}' to memory."
    except Exception as e:
        return f"Error saving memory: {e}"

def recall_memory(key: str) -> str:
    """Recalls a piece of information from memory."""
    try:
        if not os.path.exists(MEMORY_FILE):
            return "No memory file found."
        with open(MEMORY_FILE, 'r') as f:
            memory = json.load(f)
        return memory.get(key, f"Key '{key}' not found in memory.")
    except Exception as e:
        return f"Error recalling memory: {e}"

def add_to_context(note: str) -> str:
    """Adds a note to the shared context file."""
    try:
        os.makedirs(os.path.dirname(CONTEXT_FILE), exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(CONTEXT_FILE, 'a') as f:
            f.write(f"### {timestamp}\n{note}\n\n")
        return "Note added to context.md"
    except Exception as e:
        return f"Error adding to context: {e}"

def web_search(query: str) -> str:
    """Searches the web (placeholder - requires API)."""
    return "Web search is currently simulated. Please provide a web search API key in settings if available. (Note: In a real environment, I would use Tavily or Serper)."

def fetch_url(url: str) -> str:
    """Fetches a URL and returns raw content (placeholder)."""
    return f"Fetch URL stub for {url}. Requires 'requests' library."

def read_webpage(url: str) -> str:
    """Parses text from a webpage (placeholder)."""
    return f"Read Webpage stub for {url}. Requires 'requests' and 'beautifulsoup4'."
