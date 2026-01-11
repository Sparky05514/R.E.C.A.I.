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
    "ollama_base_url": "http://127.0.0.1:11434",
    "models": {
        "gemini": "gemini-3-flash-preview",
        "ollama_chat": "llama3.2:latest",
        "ollama_coder": "llama3.2:latest"
    },
    "behavior": {
        "temperature": 0.7,
        "crew_temperature": 0.2,
        "auto_save": True,
        "allowed_directories": ["."],
        "tool_confirmation": "dangerous",  # auto, dangerous, all
        "use_mcp": False,
        "use_sandbox": True,
        "sandbox_directory": "sandbox",
        "recursion_limit": 50,
        "recaizade_tools": [
            "read_file", "write_file", "list_directory", "delete_file", "run_command", "run_python", 
            "search_in_files", "move_file", "copy_file", "append_to_file", "get_file_info", 
            "get_project_structure", "analyze_code", "find_references", "save_memory", 
            "recall_memory", "add_to_context", "web_search", "fetch_url", "read_webpage"
        ],
        "coder_tools": [
            "read_file", "list_directory", "get_project_structure", "search_in_files", 
            "analyze_code", "find_references", "get_file_info", "recall_memory"
        ],
        "executor_tools": [
            "write_file", "delete_file", "run_command", "run_python", "move_file", 
            "copy_file", "append_to_file", "list_directory", "read_file"
        ],
        "reviewer_tools": [
            "read_file", "list_directory", "analyze_code", "get_file_info"
        ],
        "documenter_tools": []
    },
    "visuals": {
        "theme": "tokyo-night",
        "wrap_text": True,
        "log_verbosity": "normal"
    },
    "prompts": {
        "recaizade": None,
        "coder": None,
        "reviewer": None,
        "executor": None,
        "documenter": None
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
