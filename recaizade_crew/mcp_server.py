import os
import json
from mcp.server.fastmcp import FastMCP
import tools as tool_funcs

# Initialize FastMCP server
mcp = FastMCP("Recaizade Crew Tools")

# --- FILE OPERATIONS ---

@mcp.tool()
def read_file(filepath: str) -> str:
    """Reads a file and returns its content."""
    return tool_funcs.read_file(filepath)

@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Writes content to a file. Overwrites if exists."""
    return tool_funcs.write_file(filepath, content)

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """Lists files and directories in the given path."""
    return tool_funcs.list_directory(path)

@mcp.tool()
def delete_file(filepath: str) -> str:
    """Deletes a file."""
    return tool_funcs.delete_file(filepath)

@mcp.tool()
def move_file(source: str, destination: str) -> str:
    """Moves or renames a file."""
    return tool_funcs.move_file(source, destination)

@mcp.tool()
def copy_file(source: str, destination: str) -> str:
    """Copies a file."""
    return tool_funcs.copy_file(source, destination)

@mcp.tool()
def append_to_file(filepath: str, content: str) -> str:
    """Appends content to an existing file."""
    return tool_funcs.append_to_file(filepath, content)

# --- SYSTEM & CODE ANALYSIS ---

@mcp.tool()
def run_command(command: str) -> str:
    """Executes a shell command inside the restricted sandbox."""
    return tool_funcs.run_command(command)

@mcp.tool()
def run_python(code: str) -> str:
    """Executes Python code inside the restricted sandbox."""
    return tool_funcs.run_python(code)

@mcp.tool()
def search_in_files(pattern: str, path: str = ".") -> str:
    """Searches for a regex pattern in files within a directory."""
    return tool_funcs.search_in_files(pattern, path)

@mcp.tool()
def get_file_info(filepath: str) -> str:
    """Returns metadata about a file."""
    return tool_funcs.get_file_info(filepath)

@mcp.tool()
def get_project_structure(path: str = ".") -> str:
    """Returns a tree view of the project structure."""
    return tool_funcs.get_project_structure(path)

@mcp.tool()
def analyze_code(filepath: str) -> str:
    """Performs basic static analysis on a Python file."""
    return tool_funcs.analyze_code(filepath)

@mcp.tool()
def find_references(pattern: str, path: str = ".") -> str:
    """Finds references to a symbol (function/class name) in the project."""
    return tool_funcs.find_references(pattern, path)

# --- MEMORY & CONTEXT ---

@mcp.tool()
def save_memory(key: str, value: str) -> str:
    """Saves a piece of information to persistent memory."""
    return tool_funcs.save_memory(key, value)

@mcp.tool()
def recall_memory(query: str) -> str:
    """Recalls memory based on a query."""
    return tool_funcs.recall_memory(query)

@mcp.tool()
def add_to_context(content: str) -> str:
    """Adds a note to the shared context file."""
    return tool_funcs.add_to_context(content)

# --- WEB OPERATIONS ---

@mcp.tool()
def web_search(query: str) -> str:
    """Searches the web (placeholder)."""
    return tool_funcs.web_search(query)

@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetches a URL and returns raw content (placeholder)."""
    return tool_funcs.fetch_url(url)

@mcp.tool()
def read_webpage(url: str) -> str:
    """Parses text from a webpage (placeholder)."""
    return tool_funcs.read_webpage(url)

if __name__ == "__main__":
    mcp.run()
