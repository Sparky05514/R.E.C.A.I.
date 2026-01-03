from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static, Button, Switch, Label, TabbedContent, TabPane, Select
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.screen import ModalScreen
from textual import work, on
from rich.text import Text
from rich.markup import escape
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import re

from graph import app_graph
from config_manager import config
from agents import model_manager, refresh_prompts

class ChatMessage(Static):
    def __init__(self, message, sender, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.sender = sender

    def compose(self) -> ComposeResult:
        # Style based on sender
        color = "#7aa2f7" if self.sender == "User" else "#bb9af7"
        if self.sender == "Recaizade":
            color = "#7dcfff"
        elif self.sender in ["Coder", "Executor", "Reviewer"]:
            color = "#bb9af7"
        
        yield Static(f"[{color}][bold]{self.sender}:[/][/] {self.message}")

class SettingsScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label("Settings", id="settings-title")
            with TabbedContent():
                with TabPane("Models"):
                    yield Label("Provider")
                    yield Select([("Gemini", "gemini"), ("Ollama", "ollama")], value=config.get("provider"), id="provider-select")
                    yield Label("Google API Key")
                    yield Input(value=config.get("google_api_key"), password=True, id="api-key-input")
                    yield Label("Ollama Base URL")
                    yield Input(value=config.get("ollama_base_url"), id="ollama-url-input")
                    
                with TabPane("Behavior"):
                    yield Label("Recaizade Temperature")
                    yield Input(value=str(config.get("behavior", "temperature")), id="temp-input")
                    yield Label("Crew Temperature")
                    yield Input(value=str(config.get("behavior", "crew_temperature")), id="crew-temp-input")
                    yield Horizontal(
                        Label("Auto-Save Files"),
                        Switch(value=config.get("behavior", "auto_save"), id="auto-save-switch"),
                        classes="switch-container"
                    )

                with TabPane("Visuals"):
                    yield Label("Theme")
                    yield Select([("Tokyo Night", "tokyo-night"), ("Dracula", "dracula"), ("Light", "light")], value=config.get("visuals", "theme"), id="theme-select")
                    yield Horizontal(
                        Label("Wrap Text"),
                        Switch(value=config.get("visuals", "wrap_text"), id="wrap-switch"),
                        classes="switch-container"
                    )
            
            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="save-settings")
                yield Button("Cancel", variant="error", id="cancel-settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            config.set(self.query_one("#provider-select", Select).value, "provider")
            config.set(self.query_one("#api-key-input", Input).value, "google_api_key")
            config.set(self.query_one("#ollama-url-input", Input).value, "ollama_base_url")
            config.set(float(self.query_one("#temp-input", Input).value), "behavior", "temperature")
            config.set(float(self.query_one("#crew-temp-input", Input).value), "behavior", "crew_temperature")
            config.set(self.query_one("#auto-save-switch", Switch).value, "behavior", "auto_save")
            config.set(self.query_one("#theme-select", Select).value, "visuals", "theme")
            config.set(self.query_one("#wrap-switch", Switch).value, "visuals", "wrap_text")
            
            self.dismiss(True)
        else:
            self.dismiss(False)

class RecaizadeApp(App):
    CSS = """
    Screen {
        background: #1a1b26;
        color: #c0caf5;
        layout: grid;
        grid-size: 2;
        grid-columns: 3fr 1fr;
    }
    
    #chat-container {
        height: 100%;
        border: round #414868;
    }
    
    #log-container {
        height: 100%;
        border: round #414868;
    }
    
    #input-box {
        dock: bottom;
        margin: 1;
        border: round #414868;
        background: #24283b;
        color: #c0caf5;
    }

    #input-box:focus {
        border: tall #7aa2f7;
    }

    RichLog {
        background: #1a1b26;
        color: #c0caf5;
    }

    Header {
        background: #1a1b26;
        color: #7aa2f7;
    }

    Footer {
        background: #1a1b26;
    }

    /* Settings Styles */
    #settings-dialog {
        width: 60;
        height: 40;
        background: #24283b;
        border: thick #7aa2f7;
        padding: 1 2;
    }

    #settings-title {
        text-align: center;
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }

    .switch-container {
        height: auto;
        margin: 1 0;
    }

    .switch-container Label {
        width: 1fr;
    }

    #settings-buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    #settings-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("f2", "open_settings", "Settings"),
        ("ctrl+q", "quit", "Quit")
    ]

    def compose(self) -> ComposeResult:
        with Container(id="chat-container"):
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=config.get("visuals", "wrap_text"))
        
        with Container(id="log-container"):
            yield RichLog(id="debug-log", highlight=True, markup=True, wrap=config.get("visuals", "wrap_text"))

        yield Input(placeholder="Talk to Recaizade...", id="input-box")
        yield Header()
        yield Footer()

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(), self.apply_settings)

    def apply_settings(self, changed: bool) -> None:
        if changed:
            # Re-initialize models
            model_manager.reload_models()
            refresh_prompts()
            
            # Apply UI changes
            self.chat_log.wrap = config.get("visuals", "wrap_text")
            self.debug_log.wrap = config.get("visuals", "wrap_text")
            
            # Update Theme
            self.update_theme()
            
            # Re-render logs to apply wrap if needed
            self.chat_log.refresh()
            self.debug_log.refresh()
            
            self.debug_log.write(Text.from_markup("[bold green]System: Settings updated successfully.[/]"))

    def update_theme(self):
        theme = config.get("visuals", "theme")
        if theme == "dracula":
            bg = "#282a36"
            fg = "#f8f8f2"
            border = "#6272a4"
            acc = "#bd93f9"
        elif theme == "light":
            bg = "#ffffff"
            fg = "#000000"
            border = "#cccccc"
            acc = "#0000ff"
        else: # tokyo-night
            bg = "#1a1b26"
            fg = "#c0caf5"
            border = "#414868"
            acc = "#7aa2f7"
            
        self.screen.styles.background = bg
        self.screen.styles.color = fg
        # Update specific elements via CSS injection or style updates
        # For simplicity in this TUI, we can update the CSS variable or just set styles on containers
        self.query_one("#chat-container").styles.border = ("round", border)
        self.query_one("#log-container").styles.border = ("round", border)
        self.chat_log.styles.background = bg
        self.chat_log.styles.color = fg
        self.debug_log.styles.background = bg
        self.debug_log.styles.color = fg

    def on_mount(self):
        self.title = "Recaizade Crew"
        self.chat_log = self.query_one("#chat-log", RichLog)
        self.debug_log = self.query_one("#debug-log", RichLog)
        
        # Apply initial theme
        self.update_theme()
        
        # Initialize graph state if needed, or just keep history in memory locally
        self.conversation_history = []
        
        self.chat_log.write(Text.from_markup("[bold green]System: Welcome to Recaizade Crew![/]"))

    async def on_input_submitted(self, message: Input.Submitted):
        user_input = message.value
        message.input.value = ""
        
        if not user_input.strip():
            return

        self.chat_log.write(Text.from_markup(f"[bold green]User:[/] {escape(user_input)}"))
        
        # Add to history
        self.conversation_history.append(HumanMessage(content=user_input))
        
        # Run graph
        self.run_graph(user_input)

    @work(exclusive=True)
    async def run_graph(self, user_input):
        # We invoke the graph with the full history or just the new state depending on how we structured it.
        # LangGraph usually takes the state.
        
        initial_state = {
            "messages": self.conversation_history,
            "next_node": "",
            "task_description": "",
            "code_content": "",
            "review_status": ""
        }
        
        # Streaming approach to see steps
        async for event in app_graph.astream(initial_state):
            for key, value in event.items():
                # Value is the partial state update
                self.update_ui(self.debug_log.write, Text.from_markup(f"[bold yellow]Step:[/] {key}"))
                if "messages" in value:
                    new_messages = value["messages"]
                    # If this is a list of new messages, we display them.
                    # Since we use operator.add, the output of the node is just the new messages usually.
                    for msg in new_messages:
                        if isinstance(msg, ToolMessage):
                            # Render tool execution
                            self.update_ui(self.chat_log.write, Text.from_markup(f"[bold #e0af68]Tool ({escape(msg.name)}):[/] [dim]{escape(str(msg.content))[:200]}...[/]"))
                        else:
                            sender = "Unknown"
                            
                            # Normalize content (handle list format)
                            content = msg.content
                            if isinstance(content, list):
                                content = "".join([str(item.get("text", "")) for item in content if item.get("type") == "text"])
                            elif content is None:
                                content = ""
                            else:
                                content = str(content)
                            
                            if key == "recaizade":
                                sender = "Recaizade"
                            elif key == "coder":
                                sender = "Coder"
                            elif key == "executor":
                                sender = "Executor"
                            elif key == "reviewer":
                                sender = "Reviewer"
                            elif key == "documenter":
                                sender = "Documenter"
                            
                            # Update main chat window
                            # Check for <thinking> blocks
                            import re
                            parts = re.split(r"(<thinking>.*?</thinking>)", content, flags=re.DOTALL)
                            
                            for part in parts:
                                if not part.strip(): continue
                                
                                if part.strip().startswith("<thinking>"):
                                    # Style thinking block
                                    clean_thinking = part.replace("<thinking>", "").replace("</thinking>", "").strip()
                                    self.update_ui(self.chat_log.write, Text.from_markup(f"[dim italic]{escape(clean_thinking)}[/]"))
                                elif "[SYSTEM ALERT]" in part:
                                    self.update_ui(self.chat_log.write, Text.from_markup(f"[bold white on red]{escape(part)}[/]"))
                                else:
                                    sender_color = "#7dcfff" if sender == "Recaizade" else "#bb9af7"
                                    self.update_ui(self.chat_log.write, Text.from_markup(f"[bold {sender_color}]{sender}:[/] {escape(part)}"))
                        
                        # Upadte history to keep sync (though graph keeps its own usually, 
                        # but we passed 'messages' as input. 
                        # Ideally we should update self.conversation_history with the OUTPUT of the graph
                        # for the next turn.
                        
                        # Actually 'event' contains the result of the node.
                        # So we should append these to our local history if we want persistence across turns
                        # if the graph is stateless between calls (which it is here as we re-invoke).
                        if msg not in self.conversation_history:
                            self.conversation_history.append(msg)
                            
    def update_ui(self, func, *args):
        # Textual helper to update UI from worker
        # Since run_graph is an async worker on the main thread (default), we don't need call_from_thread
        # warning: if we move to thread=True, we might need call_from_thread again.
        func(*args)

if __name__ == "__main__":
    app = RecaizadeApp()
    app.run()
