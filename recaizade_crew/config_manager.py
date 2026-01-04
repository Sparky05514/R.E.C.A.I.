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
    },
    "visuals": {
        "theme": "tokyo-night",
        "wrap_text": True,
        "log_verbosity": "normal"
    },
    "prompts": {
        "recaizade": None, # Use default if None
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
