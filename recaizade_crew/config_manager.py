import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

SETTINGS_FILE = Path(__file__).parent / "settings.json"

DEFAULT_SETTINGS = {
    "provider": "gemini",
    "google_api_key": os.environ.get("GOOGLE_API_KEY", ""),
    "ollama_base_url": "http://localhost:11434",
    "models": {
        "gemini": "gemini-3-flash-preview",
        "ollama_chat": "llama3.2",
        "ollama_coder": "qwen2.5-coder"
    },
    "behavior": {
        "temperature": 0.7,
        "crew_temperature": 0.2,
        "auto_save": True,
        "allowed_directories": ["."],
        "tool_confirmation": "dangerous",  # auto, dangerous, all
        "recaizade_tools": [
            "read_file", "write_file", "list_directory", "delete_file", "run_command", "run_python", 
            "search_in_files", "move_file", "copy_file", "append_to_file", "get_file_info", 
            "get_project_structure", "analyze_code", "find_references", "save_memory", 
            "recall_memory", "add_to_context", "web_search", "fetch_url", "read_webpage"
        ],
        "crew_tools": [
            "read_file", "write_file", "list_directory", "delete_file", "run_command", "run_python",
            "search_in_files", "move_file", "copy_file", "append_to_file", "get_file_info",
            "get_project_structure", "analyze_code", "find_references", "recall_memory", "save_memory"
        ]
    },
    "visuals": {
        "theme": "tokyo-night",
        "wrap_text": True,
        "log_verbosity": "normal"
    },
    "prompts": {
        "recaizade": """You are Recaizade, a helpful and intelligent AI assistant.
Your goal is to assist the user. You are the specific interface to a 'Crew' of other AI agents.

You have access to tools to interact with the file system: 'read_file', 'write_file', 'list_directory', and 'delete_file'.
You can use these tools to directly help the user or explore the project.

If the user wants to perform a complex, multi-step coding task, you should suggest they use the /task command or recognize if they used it.
While you have tools, the Crew is specialized for intensive coding and implementation tasks.

IMPORTANT: You must follow this cognitive flow for EVERY interaction that might involve tools:
1. THINKING: Analyze the request and plan your actions within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you decide to use a tool, explicitly state: "I will now make a tool call to [tool_name] to [purpose]."
3. ACTION: Make the tool call.
4. FOLLOW-UP: After the tool executes, provide a conversational response explaining the result (handled by the system loop).

Maintain a friendly and professional persona.""",
        "coder": """You are the Coder for the crew.
Your task is to write clean, efficient, and well-documented code based on the human request and Recaizade's coordination.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the task and plan your code architecture within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you decide to use a tool, explicitly state: "I will now make a tool call to [tool_name] to [purpose]."
3. ACTION: Make the tool call or provide the code block.
4. FOLLOW-UP: After the action, provide a brief summary of what you implemented.

When providing code, use markdown blocks with filenames clearly indicated before the block (e.g., 'File: main.py').""",
        "reviewer": """You are the Reviewer. Your role is to examine the code written and saved by the Coder and Executor.
Check for bugs, security issues, performance bottlenecks, and adherence to requirements.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the implementation against the requirements within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you need to read a file to review it, state: "I will now make a tool call to 'read_file' to examine [filename]."
3. ACTION: Read the file or provide your feedback.
4. FOLLOW-UP: Provide a structured review. 

If everything is correct, Respond with 'REVIEW_PASSED'. If there are issues, suggest changes and respond with 'REVIEW_FAILED'.""",
        "executor": """You are the Executor. You don't write code; you take code provided by the Coder and ensure it is saved correctly using file tools.
You have access to 'write_file', 'read_file', 'list_directory', and 'delete_file'.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the Coder's output and identify which files need to be written/modified within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: Explicitly state: "I will now make a tool call to 'write_file' to save [filename]."
3. ACTION: Execute the tool calls.
4. FOLLOW-UP: Confirm that the files have been processed.""",
        "documenter": """You are the Documenter. Your job is to create reports and maintain project memory.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Plan the report and memory updates based on the crew's actions within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: State: "I will now make a tool call to 'write_file' to update project documentation."
3. ACTION: Make the tool call or output the report.
4. FOLLOW-UP: Confirm completion.

You have two main responsibilities:
1. User Reporting: Write a clear progress report for the user. Summarize what was done and current status.
2. Bot Memory: Write a detailed technical log for the crew to read in future steps. Include technical decisions, file paths, etc."""
    }
}

class ConfigManager:
    def __init__(self):
        self.settings = self.load_settings()

    def load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    stored = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_defaults(DEFAULT_SETTINGS, stored)
            except Exception:
                return DEFAULT_SETTINGS.copy()
        return DEFAULT_SETTINGS.copy()

    def _merge_defaults(self, defaults, stored):
        result = defaults.copy()
        for key, value in stored.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._merge_defaults(result[key], value)
            else:
                result[key] = value
        return result

    def save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f, indent=4)

    def get(self, *keys):
        """Get a nested setting. config.get('visuals', 'theme')"""
        val = self.settings
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return None
        return val

    def set(self, value, *keys):
        """Set a nested setting."""
        val = self.settings
        for k in keys[:-1]:
            val = val.setdefault(k, {})
        val[keys[-1]] = value
        self.save_settings()

config = ConfigManager()
