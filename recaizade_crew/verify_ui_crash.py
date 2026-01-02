from langchain_core.messages import AIMessage
from rich.console import Console

# Mock UI logic to verify list content parsing
def verify_ui_parsing():
    # Simulate Gemini response structure
    content_list = [
        {
            'type': 'text',
            'text': "<thinking>\nI need to check files.\n</thinking>\nI will now call list_directory to see files.",
            'extras': {}
        }
    ]
    
    print("Testing List Content Parsing...")
    
    # Logic extracted from ui.py fix
    content = content_list
    if isinstance(content, list):
        content = "".join([str(item.get("text", "")) for item in content if item.get("type") == "text"])
    elif content is None:
        content = ""
    else:
        content = str(content)
        
    print(f"Normalized Content: '{content}'")
    
    import re
    parts = re.split(r"(<thinking>.*?</thinking>)", content, flags=re.DOTALL)
    
    for part in parts:
        if not part.strip(): continue
        
        if part.strip().startswith("<thinking>"):
            clean = part.replace("<thinking>", "").replace("</thinking>", "").strip()
            print(f"[FOUND THINKING]: {clean}")
        else:
            print(f"[FOUND TEXT]: {part.strip()}")
            
    if len(parts) >= 3:
        print("SUCCESS: Content parsed correctly from list structure.")
    else:
        print("FAILURE: parsing failed.")

if __name__ == "__main__":
    verify_ui_parsing()
