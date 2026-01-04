from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static, Button, Switch, Label, TabbedContent, TabPane, Select, ListItem, ListView, OptionList
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

class SettingItem(ListItem):
    def __init__(self, title: str, subtitle: str, key: str, value: any, setting_type: str = "text", options: list = None):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.key = key
        self.setting_value = value
        self.setting_type = setting_type
        self.options = options

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical():
                yield Label(self.title, classes="setting-title")
                yield Label(str(self.subtitle), classes="setting-subtitle")

class SettingsScreen(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("enter", "select_or_edit", "Select/Edit"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="settings-container"):
            with Horizontal(id="settings-layout"):
                with Vertical(id="settings-sidebar"):
                    yield Input(placeholder="Search settings...", id="settings-search")
                    with ListView(id="settings-list"):
                        yield SettingItem("Provider", config.get("provider"), "provider", config.get("provider"), "select", [("Gemini", "gemini"), ("Ollama", "ollama")])
                        yield SettingItem("Google API Key", "********" if config.get("google_api_key") else "Not Set", "google_api_key", config.get("google_api_key"))
                        yield SettingItem("Ollama Base URL", config.get("ollama_base_url"), "ollama_base_url", config.get("ollama_base_url"))
                        yield SettingItem("Recaizade Temperature", str(config.get("behavior", "temperature")), "temperature", config.get("behavior", "temperature"))
                        yield SettingItem("Crew Temperature", str(config.get("behavior", "crew_temperature")), "crew_temperature", config.get("behavior", "crew_temperature"))
                        yield SettingItem("Theme", config.get("visuals", "theme"), "theme", config.get("visuals", "theme"), "select", [("Tokyo Night", "tokyo-night"), ("Dracula", "dracula"), ("Light", "light")])
                        yield SettingItem("Auto-Save Files", "Toggle auto-save behavior", "auto_save", config.get("behavior", "auto_save"), "switch")
                        yield SettingItem("Wrap Text", "Toggle text wrapping in logs", "wrap_text", config.get("visuals", "wrap_text"), "switch")
                
                with Vertical(id="settings-config-pane"):
                    yield Static("Select a setting to edit", id="config-placeholder")
            
            yield Label("Navigate: [bold]↑↓[/] | Edit: [bold]Enter[/] | Close: [bold]Esc[/]", id="settings-footer")

    def on_mount(self):
        self.query_one("#settings-search").focus()

    def action_select_or_edit(self):
        # If search is focused and list has items, focus the list
        if self.query_one("#settings-search").has_focus:
            lst = self.query_one("#settings-list")
            if lst.visible_children:
                lst.index = 0
                lst.focus()
        # If list is focused, focus the first interactive element in config pane
        elif self.query_one("#settings-list").has_focus:
            config_pane = self.query_one("#settings-config-pane")
            inputs = config_pane.query("Input, Select, Switch")
            if inputs:
                inputs.first().focus()
        # If an input/select/switch is focused, submitting it will trigger its own event

    @on(Input.Changed, "#settings-search")
    def filter_settings(self, event: Input.Changed):
        search_term = event.value.lower()
        for item in self.query(SettingItem):
            item.display = search_term in item.title.lower() or search_term in str(item.subtitle).lower()

    @on(ListView.Highlighted)
    def update_config_pane(self, event: ListView.Highlighted):
        item = event.item
        if not item: return
        
        pane = self.query_one("#settings-config-pane")
        pane.query("*").remove()
        
        with self.app.batch_update():
            pane.mount(Label(f"Editing: {item.title}", classes="config-title"))
            if item.setting_type == "text":
                pane.mount(Input(value=str(item.setting_value), id=f"edit-{item.key}"))
            elif item.setting_type == "select":
                pane.mount(Select(item.options, value=item.setting_value, id=f"edit-{item.key}"))
            elif item.setting_type == "switch":
                pane.mount(Horizontal(
                    Label("Enabled"),
                    Switch(value=item.setting_value, id=f"edit-{item.key}"),
                    classes="switch-row"
                ))
            
            pane.mount(Static(f"\n{item.subtitle}", classes="config-description"))

    @on(Input.Submitted)
    @on(Select.Changed)
    @on(Switch.Changed)
    def handle_value_change(self, event):
        # Identify which setting we are editing
        item = self.query_one("#settings-list").highlighted_child
        if not item: return

        new_value = None
        if isinstance(event, Input.Submitted):
            new_value = event.value
        elif isinstance(event, Select.Changed):
            new_value = event.value
        elif isinstance(event, Switch.Changed):
            new_value = event.value

        if new_value is not None:
            self.save_setting(item, new_value)
            # Update item visuals
            item.setting_value = new_value
            if item.setting_type != "switch": # Switches in sidebar update via event or we can just ignore them there
                item.query_one(".setting-subtitle").update(str(new_value))
            
            # Show success briefly
            self.notify(f"Saved {item.title}", severity="information", timeout=2)

    def save_setting(self, item: SettingItem, value: any):
        if item.key == "provider":
            config.set(value, "provider")
        elif item.key == "google_api_key":
            config.set(value, "google_api_key")
        elif item.key == "ollama_base_url":
            config.set(value, "ollama_base_url")
        elif item.key == "temperature":
            config.set(float(value), "behavior", "temperature")
        elif item.key == "crew_temperature":
            config.set(float(value), "behavior", "crew_temperature")
        elif item.key == "theme":
            config.set(value, "visuals", "theme")
        elif item.key == "auto_save":
            config.set(value, "behavior", "auto_save")
        elif item.key == "wrap_text":
            config.set(value, "visuals", "wrap_text")
        
        self.app.apply_settings(True)

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

    /* Settings Palette Styles */
    #settings-container {
        width: 100;
        height: 35;
        background: #24283b;
        border: thick #7aa2f7;
        padding: 0;
        align: center middle;
    }

    #settings-layout {
        height: 1fr;
    }

    #settings-sidebar {
        width: 40;
        border-right: solid #414868;
    }

    #settings-search {
        border: none;
        background: #1a1b26;
        color: #c0caf5;
        margin: 0;
        padding: 1 2;
    }

    #settings-search:focus {
        border: none;
        background: #24283b;
    }

    #settings-list {
        height: 1fr;
        background: #1a1b26;
    }

    SettingItem {
        padding: 0 1;
        border-bottom: solid #414868;
        height: 4;
    }

    SettingItem:focus {
        background: #2e3440;
    }

    SettingItem .setting-title {
        text-style: bold;
        color: #7aa2f7;
        margin-top: 1;
    }

    #settings-config-pane {
        width: 1fr;
        background: #24283b;
        padding: 2;
    }

    .config-title {
        text-style: bold;
        color: #bb9af7;
        margin-bottom: 1;
    }

    .config-description {
        color: #565f89;
        margin-top: 1;
    }

    .switch-row {
        height: auto;
        align: left middle;
    }

    .switch-row Label {
        width: 1fr;
    }

    #settings-footer {
        text-align: center;
        width: 100%;
        background: #1a1b26;
        color: #565f89;
        padding: 0 1;
    }

    #settings-config-pane Input, #settings-config-pane Select {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("f2", "open_settings", "Settings"),
        ("ctrl+l", "clear_chat", "Clear Chat"),
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

    def action_clear_chat(self) -> None:
        self.chat_log.clear()
        self.debug_log.clear()
        self.conversation_history = []
        self.chat_log.write(Text.from_markup("[bold green]System: Chat cleared and history reset.[/]"))

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
