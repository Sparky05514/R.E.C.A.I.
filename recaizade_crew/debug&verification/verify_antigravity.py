import re
from rich.text import Text
from rich.markup import escape

# Simulation of msg structure and UI parsing logic
class MockMsg:
    def __init__(self, content, type="ai", name=None):
        self.content = content
        self.type = type
        self.name = name

def simulate_ui_render(msg, sender, key):
    print(f"\n--- RENDERING MESSAGE FROM {sender} (Node: {key}) ---")
    
    # Logic from ui.py
    content = msg.content
    if isinstance(content, list):
        content = "".join([str(item.get("text", "")) for item in content if item.get("type") == "text"])
    elif content is None:
        content = ""
    else:
        content = str(content)
        
    if isinstance(msg, MockMsg) and msg.type == "ai":
        parts = re.split(r"(<thinking>.*?</thinking>)", content, flags=re.DOTALL)
        for part in parts:
            if not part.strip(): continue
            if part.strip().startswith("<thinking>"):
                clean = part.replace("<thinking>", "").replace("</thinking>", "").strip()
                print(f"UI DISPLAY (Thinking): [dim italic]{clean}[/]")
            elif "[SYSTEM ALERT]" in part:
                print(f"UI DISPLAY (Alert): [bold white on red]{part}[/]")
            else:
                print(f"UI DISPLAY (Text): [bold cyan]{sender}:[/] {part.strip()}")
                
    elif isinstance(msg, MockMsg) and msg.type == "tool":
        print(f"UI DISPLAY (Tool): [bold blue]Tool ({msg.name}):[/] [dim]{str(content)[:50]}...[/]")

def test_flow():
    # 1. Gemini-style list content
    gemini_msg = MockMsg(content=[{'type': 'text', 'text': "<thinking>I need to plan.</thinking>\nI'll call a tool."}], type="ai")
    simulate_ui_render(gemini_msg, "Recaizade", "recaizade")

    # 2. Tool message
    tool_msg = MockMsg(content="File saved successfully", type="tool", name="write_file")
    simulate_ui_render(tool_msg, "Executor", "executor")

    # 3. Follow-up message (Antigravity style)
    followup_msg = MockMsg(content="<thinking>The tool worked.</thinking>\nTask complete.", type="ai")
    simulate_ui_render(followup_msg, "Coder", "coder")

    # 4. System Alert
    alert_msg = MockMsg(content="[SYSTEM ALERT] API Error: Quota exceeded. Switching to Ollama...", type="ai")
    simulate_ui_render(alert_msg, "Recaizade", "recaizade")

if __name__ == "__main__":
    test_flow()
