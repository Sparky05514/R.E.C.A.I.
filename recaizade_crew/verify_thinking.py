from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from rich.console import Console

# Mock UI logic to verify parsing
def verify_ui_parsing():
    content = """<thinking>
I need to check the current directory to see what files exist.
</thinking>
I will now make a tool call to 'list_directory' to see the current files.
"""
    
    print("Testing Content Parsing...")
    import re
    parts = re.split(r"(<thinking>.*?</thinking>)", content, flags=re.DOTALL)
    
    for part in parts:
        if not part.strip(): continue
        
        if part.strip().startswith("<thinking>"):
            clean = part.replace("<thinking>", "").replace("</thinking>", "").strip()
            print(f"[FOUND THINKING]: {clean}")
        else:
            print(f"[FOUND TEXT]: {part.strip()}")
            
    if len(parts) >= 3: # empty, thinking, text, ...
        print("SUCCESS: Content parsed into thinking and text blocks.")
    else:
        print("FAILURE: parsing failed.")

if __name__ == "__main__":
    verify_ui_parsing()
