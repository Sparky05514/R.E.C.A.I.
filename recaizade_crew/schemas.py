from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ReadFileArgs(BaseModel):
    filepath: str = Field(..., description="The path to the file to read.")

class WriteFileArgs(BaseModel):
    filepath: str = Field(..., description="The path to the file to write.")
    content: str = Field(..., description="The content to write to the file.")

class ListDirectoryArgs(BaseModel):
    path: str = Field(".", description="The directory path to list.")

class DeleteFileArgs(BaseModel):
    filepath: str = Field(..., description="The path to the file to delete.")

class RunCommandArgs(BaseModel):
    command: str = Field(..., description="The shell command to execute.")

class RunPythonArgs(BaseModel):
    code: str = Field(..., description="The Python code to execute.")

class SearchInFilesArgs(BaseModel):
    pattern: str = Field(..., description="The regex pattern to search for.")
    path: str = Field(".", description="The directory to search in.")

class MoveFileArgs(BaseModel):
    source: str = Field(..., description="Source path.")
    destination: str = Field(..., description="Destination path.")

class CopyFileArgs(BaseModel):
    source: str = Field(..., description="Source path.")
    destination: str = Field(..., description="Destination path.")

class AppendToFileArgs(BaseModel):
    filepath: str = Field(..., description="Path to file.")
    content: str = Field(..., description="Content to append.")

class GetFileInfoArgs(BaseModel):
    filepath: str = Field(..., description="Path to file.")

class SaveMemoryArgs(BaseModel):
    key: str = Field(..., description="Memory key.")
    value: str = Field(..., description="Memory value.")

class RecallMemoryArgs(BaseModel):
    query: str = Field(..., description="Query to search memory.")

class AddToContextArgs(BaseModel):
    content: str = Field(..., description="Information to add to permanent context.")

class WebSearchArgs(BaseModel):
    query: str = Field(..., description="Search query.")

class FetchUrlArgs(BaseModel):
    url: str = Field(..., description="URL to fetch.")

class ReadWebpageArgs(BaseModel):
    url: str = Field(..., description="URL of the webpage to read.")

# Mapping for graph validation
SCHEMA_MAP = {
    "read_file": ReadFileArgs,
    "write_file": WriteFileArgs,
    "list_directory": ListDirectoryArgs,
    "delete_file": DeleteFileArgs,
    "run_command": RunCommandArgs,
    "run_python": RunPythonArgs,
    "search_in_files": SearchInFilesArgs,
    "move_file": MoveFileArgs,
    "copy_file": CopyFileArgs,
    "append_to_file": AppendToFileArgs,
    "get_file_info": GetFileInfoArgs,
    "save_memory": SaveMemoryArgs,
    "recall_memory": RecallMemoryArgs,
    "add_to_context": AddToContextArgs,
    "web_search": WebSearchArgs,
    "fetch_url": FetchUrlArgs,
    "read_webpage": ReadWebpageArgs
}
