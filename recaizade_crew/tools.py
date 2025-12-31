import os
import shutil
from pathlib import Path

WORKING_DIRECTORY = os.getcwd()

def _is_safe_path(filepath):
    # Ensure usage is within the working directory or subdirectories
    abs_path = os.path.abspath(filepath)
    return abs_path.startswith(WORKING_DIRECTORY)

def read_file(filepath: str) -> str:
    """Reads a file and returns its content."""
    if not _is_safe_path(filepath):
        return f"Error: Access denied to path {filepath}"
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath: str, content: str) -> str:
    """Writes content to a file. Overwrites if exists."""
    if not _is_safe_path(filepath):
        return f"Error: Access denied to path {filepath}"
    try:
        # Create directories if they don't exist
        dirname = os.path.dirname(filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"

def list_directory(path: str = ".") -> str:
    """Lists files and directories in the given path."""
    if not _is_safe_path(path):
         return f"Error: Access denied to path {path}"
    try:
        items = os.listdir(path)
        return "\n".join(items) if items else "(Empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"

def delete_file(filepath: str) -> str:
    """Deletes a file."""
    if not _is_safe_path(filepath):
        return f"Error: Access denied to path {filepath}"
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            return f"Successfully deleted {filepath}"
        else:
            return f"Error: {filepath} is not a file"
    except Exception as e:
        return f"Error deleting file: {e}"
