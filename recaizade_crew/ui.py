from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static, Button, Switch, Label, Select, ListItem, ListView, TextArea
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.screen import ModalScreen
from textual import work, on
from rich.text import Text
from rich.markup import escape
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import re
import json

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

class ToolConfirmationScreen(ModalScreen):
    """Modal screen for confirming tool execution."""
    def __init__(self, tool_call: dict, **kwargs):
        super().__init__(**kwargs)
        self.tool_call = tool_call

    def compose(self) -> ComposeResult:
        tool_name = self.tool_call["name"]
        args = json.dumps(self.tool_call["args"], indent=2)
        
        with Container(id="confirmation-container"):
            yield Label("⚠️ TOOL CONFIRMATION REQUIRED", id="confirmation-title")
            yield Label(f"Agent wants to execute tool: [bold cyan]{tool_name}[/]", id="confirmation-info")
            yield Static(f"Arguments:\n{args}", id="confirmation-args")
            with Horizontal(id="confirmation-buttons"):
                yield Button("Approve", variant="success", id="btn-approve")
                yield Button("Deny", variant="error", id="btn-deny")
            yield Label("Approval will allow the tool to execute. Denial will skip it.", id="confirmation-hint")

    @on(Button.Pressed, "#btn-approve")
    def approve(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn-deny")
    def deny(self):
        self.dismiss(False)

class SettingsScreen(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("ctrl+p", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="settings-container"):
            yield Input(placeholder="Search settings...", id="settings-search")
            with Horizontal(id="settings-body"):
                with Vertical(id="settings-list-container"):
                    with ListView(id="settings-list"):
                        # Model Configuration
                        yield SettingItem("Provider", config.get("provider"), "provider", config.get("provider"), "select", [("Gemini", "gemini"), ("Ollama", "ollama")])
                        yield SettingItem("Gemini Model", config.get("models", "gemini"), "models.gemini", config.get("models", "gemini"))
                        yield SettingItem("Ollama Chat Model", config.get("models", "ollama_chat"), "models.ollama_chat", config.get("models", "ollama_chat"))
                        yield SettingItem("Ollama Coder Model", config.get("models", "ollama_coder"), "models.ollama_coder", config.get("models", "ollama_coder"))
                        
                        # API Setup / API Keys
                        yield SettingItem("Google API Key", "********" if config.get("google_api_key") else "Not Set", "google_api_key", config.get("google_api_key"))
                        yield SettingItem("Ollama Base URL", config.get("ollama_base_url"), "ollama_base_url", config.get("ollama_base_url"))
                        
                        # Behavior
                        yield SettingItem("Recaizade Temp", str(config.get("behavior", "temperature")), "behavior.temperature", config.get("behavior", "temperature"))
                        yield SettingItem("Crew Temp", str(config.get("behavior", "crew_temperature")), "behavior.crew_temperature", config.get("behavior", "crew_temperature"))
                        yield SettingItem("Auto-Save", "Toggle auto-save behavior", "behavior.auto_save", config.get("behavior", "auto_save"), "switch")
                        yield SettingItem("Allowed Dirs", str(config.get("behavior", "allowed_directories")), "behavior.allowed_directories", ",".join(config.get("behavior", "allowed_directories")))
                        yield SettingItem("Tool Confirmation", config.get("behavior", "tool_confirmation"), "behavior.tool_confirmation", config.get("behavior", "tool_confirmation"), "select", [("Auto", "auto"), ("Dangerous Only", "dangerous"), ("All Tools", "all")])
                        yield SettingItem("Recaizade Tools", "Tools available to leader", "behavior.recaizade_tools", ",".join(config.get("behavior", "recaizade_tools")), "large_text")
                        yield SettingItem("Crew Tools", "Tools available to crew", "behavior.crew_tools", ",".join(config.get("behavior", "crew_tools")), "large_text")

                        # Visuals
                        yield SettingItem("Theme", config.get("visuals", "theme"), "visuals.theme", config.get("visuals", "theme"), "select", [("Tokyo Night", "tokyo-night"), ("Dracula", "dracula"), ("Light", "light")])
                        yield SettingItem("Wrap Text", "Toggle text wrapping in logs", "visuals.wrap_text", config.get("visuals", "wrap_text"), "switch")
                        yield SettingItem("Log Verbosity", config.get("visuals", "log_verbosity"), "visuals.log_verbosity", config.get("visuals", "log_verbosity"), "select", [("Normal", "normal"), ("Verbose", "verbose"), ("Quiet", "quiet")])
                
                        # Prompts
                        yield SettingItem("Recaizade Prompt", "System prompt for leader", "prompts.recaizade", config.get("prompts", "recaizade"), "large_text")
                        yield SettingItem("Coder Prompt", "System prompt for coder", "prompts.coder", config.get("prompts", "coder"), "large_text")
                        yield SettingItem("Reviewer Prompt", "System prompt for reviewer", "prompts.reviewer", config.get("prompts", "reviewer"), "large_text")
                        yield SettingItem("Executor Prompt", "System prompt for executor", "prompts.executor", config.get("prompts", "executor"), "large_text")
                        yield SettingItem("Documenter Prompt", "System prompt for documenter", "prompts.documenter", config.get("prompts", "documenter"), "large_text")
                        
                with Vertical(id="settings-config-pane"):
                    yield Static("Choose a setting to configure", id="settings-placeholder")
            
            yield Label(" [bold]CTRL+P[/] Settings | [bold]↑↓[/] Navigate | [bold]ENTER[/] Edit | [bold]ESC[/] Close ", id="settings-footer")

    def on_mount(self):
        self.title = "Settings"
        self.query_one("#settings-search").focus()

    @on(Input.Changed, "#settings-search")
    def filter_settings(self, event: Input.Changed):
        search_term = event.value.lower()
        for item in self.query(SettingItem):
            item.display = search_term in item.title.lower() or search_term in str(item.subtitle).lower()

    @on(ListView.Highlighted)
    def switch_config(self, event: ListView.Highlighted):
        item = event.item
        if not item: return
        
        pane = self.query_one("#settings-config-pane")
        pane.query("*").remove()
        
        # Create a safe ID by replacing dots with underscores
        safe_id = item.key.replace('.', '_')
        
        pane.mount(Label(item.title, classes="config-title"))
        if item.setting_type == "text":
            pane.mount(Input(value=str(item.setting_value or ""), id=f"edit-{safe_id}"))
        elif item.setting_type == "large_text":
            pane.mount(TextArea(str(item.setting_value or ""), id=f"edit-{safe_id}"))
        elif item.setting_type == "select":
            # Ensure the value is in the options or use the first option as default
            val = item.setting_value
            if val not in [opt[1] for opt in item.options]:
                val = item.options[0][1] if item.options else None
            pane.mount(Select(item.options, value=val, id=f"edit-{safe_id}"))
        elif item.setting_type == "switch":
            pane.mount(Horizontal(
                Label("Enabled"),
                Switch(value=item.setting_value, id=f"edit-{safe_id}"),
                classes="switch-row"
            ))
        
        pane.mount(Static(f"\n{item.subtitle}", classes="config-description"))

    def on_key(self, event):
        if event.key == "enter":
            if self.query_one("#settings-search").has_focus:
                # Move to list
                lst = self.query_one("#settings-list")
                if lst.visible_children:
                    lst.focus()
            elif self.query_one("#settings-list").has_focus:
                # Move to edit pane
                pane = self.query_one("#settings-config-pane")
                inputs = pane.query("Input, Select, Switch, TextArea")
                if inputs:
                    inputs.first().focus()

    @on(Input.Submitted)
    @on(Select.Changed)
    @on(Switch.Changed)
    def commit_change(self, event):
        # We need to know which item is highlighted to save correctly
        lst = self.query_one("#settings-list")
        item = lst.highlighted_child
        if not item: return

        # Extract path from key (e.g. "models.gemini" -> ["models", "gemini"])
        key_parts = item.key.split('.')
        
        new_value = None
        if isinstance(event, Input.Submitted):
            new_value = event.value
        elif isinstance(event, Select.Changed):
            new_value = event.value
        elif isinstance(event, Switch.Changed):
            new_value = event.value
        elif isinstance(event, TextArea.Changed):
            new_value = event.text_area.text

        if new_value is not None:
            # Handle numeric values for temperatures
            if "temperature" in item.key or "temp" in item.key.lower():
                try:
                    new_value = float(new_value)
                except ValueError:
                    return

            # Handle list for directories or tools
            if item.key in ["behavior.allowed_directories", "behavior.recaizade_tools", "behavior.crew_tools"]:
                new_value = [d.strip() for d in str(new_value).split(',') if d.strip()]

            config.set(new_value, *key_parts)
            item.setting_value = new_value
            if item.setting_type not in ["switch", "large_text"]:
                item.query_one(".setting-subtitle").update(str(new_value))
            
            self.notify(f"Updated {item.title}", timeout=2)
            self.app.apply_settings(True)

class RecaizadeApp(App):
    ENABLE_COMMAND_PALETTE = False  # Disable Textual's built-in palette, we use our own Settings screen
    
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
        border: solid #7aa2f7;
        background: #292e42;
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

    /* Settings Screen Styles */
    #settings-container {
        width: 100;
        height: 40;
        background: #1a1b26;
        border: thick #7aa2f7;
        padding: 0;
        align: center top;
        margin-top: 2;
    }

    #settings-search {
        border: none;
        background: #16161e;
        color: #7aa2f7;
        padding: 1 2;
        text-style: bold;
    }

    #settings-search:focus {
        border: none;
    }

    #settings-body {
        height: 1fr;
    }

    #settings-list-container {
        width: 40;
        border-right: solid #414868;
        background: #1a1b26;
    }

    #settings-list {
        background: transparent;
        height: 1fr;
        scrollbar-gutter: stable;
    }

    SettingItem {
        padding: 0 1;
        border-bottom: solid #414868;
        height: 3;
    }

    SettingItem:focus {
        background: #24283b;
    }

    SettingItem .setting-title {
        color: #c0caf5;
        text-style: bold;
    }

    SettingItem .setting-subtitle {
        color: #565f89;
        text-style: italic;
    }

    #settings-config-pane {
        width: 1fr;
        padding: 2;
        background: #1a1b26;
    }

    .config-title {
        color: #bb9af7;
        text-style: bold;
        margin-bottom: 1;
    }

    .config-description {
        color: #565f89;
    }

    #settings-footer {
        background: #16161e;
        color: #565f89;
        text-align: center;
        padding: 0 1;
    }

    /* Input focus in settings */
    #settings-config-pane Input, #settings-config-pane Select, #settings-config-pane TextArea {
        width: 100%;
        background: #24283b;
        border: solid #7aa2f7;
    }

    #settings-config-pane TextArea {
        height: 10;
        border: solid #414868;
    }
    
    /* Confirmation Modal Styles */
    #confirmation-container {
        width: 60;
        height: auto;
        padding: 2;
        background: #1a1b26;
        border: thick #7aa2f7;
    }
    #confirmation-title {
        text-align: center;
        width: 100%;
        text-style: bold;
        color: #ff9e64;
        margin-bottom: 1;
    }
    #confirmation-info {
        margin-bottom: 1;
    }
    #confirmation-args {
        background: #24283b;
        padding: 1;
        margin-bottom: 1;
        height: auto;
        max-height: 15;
    }
    #confirmation-buttons {
        align: center middle;
        height: 3;
        margin-bottom: 1;
    }
    #confirmation-buttons Button {
        margin: 0 2;
    }
    #confirmation-hint {
        text-align: center;
        text-style: italic;
        color: #565f89;
    }
    """

    BINDINGS = [
        ("ctrl+p", "open_settings", "Settings"),
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
        yield Footer(show_command_palette=False)

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
            "review_status": "",
            "waiting_confirmation": False,
            "pending_tool": {}
        }
        
        # Streaming approach to see steps
        async for event in app_graph.astream(initial_state):
            # Check for waiting_confirmation in state
            if "waiting_confirmation" in event and event["waiting_confirmation"]:
                tool_call = event["pending_tool"]
                self.app.push_screen(ToolConfirmationScreen(tool_call), self.handle_confirmation)
                return

            for key, value in event.items():
                if isinstance(value, dict) and value.get("waiting_confirmation"):
                    tool_call = value["pending_tool"]
                    self.app.push_screen(ToolConfirmationScreen(tool_call), self.handle_confirmation)
                    return
                
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
                            # Strip out XML-like tags that models sometimes output
                            import re
                            
                            # First, extract and handle thinking blocks
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
                                    # Clean up other XML-like tags (announcement, action, etc.)
                                    clean_part = re.sub(r"</?\w+>", "", part).strip()
                                    if clean_part:
                                        sender_color = "#7dcfff" if sender == "Recaizade" else "#bb9af7"
                                        self.update_ui(self.chat_log.write, Text.from_markup(f"[bold {sender_color}]{sender}:[/] {escape(clean_part)}"))
                        
                        # Upadte history to keep sync (though graph keeps its own usually, 
                        # but we passed 'messages' as input. 
                        # Ideally we should update self.conversation_history with the OUTPUT of the graph
                        # for the next turn.
                        
                        # Actually 'event' contains the result of the node.
                        # So we should append these to our local history if we want persistence across turns
                        # if the graph is stateless between calls (which it is here as we re-invoke).
                        if msg not in self.conversation_history:
                            self.conversation_history.append(msg)
                            
    def handle_confirmation(self, approved: bool):
        """Callback from ToolConfirmationScreen."""
        if not self.conversation_history: return
        
        # Find the last message that was a tool-calling AI message
        # In Recaizade Crew, the graph interrupts BEFORE tool execution.
        # So the last message in history is the AIMessage with tool calls.
        
        last_msg = self.conversation_history[-1]
        if not (isinstance(last_msg, AIMessage) and last_msg.tool_calls):
            # Something went wrong with history sync
            self.chat_log.write(Text.from_markup("[bold red]System Error: Could not find tool call to confirm.[/]"))
            return

        tool_call = last_msg.tool_calls[0] # For now, handle the first one
        tool_name = tool_call["name"]
        tool_id = tool_call["id"]

        if approved:
            self.chat_log.write(Text.from_markup(f"[bold green]System: Tool approved.[/]"))
            # Add an invisible "approval" message to history
            approval_msg = HumanMessage(content=f"APPROVE_TOOL:{tool_name}:{tool_id}")
            self.conversation_history.append(approval_msg)
            # Re-run graph - it will now see the approval and execute
            self.run_graph("") 
        else:
            self.chat_log.write(Text.from_markup(f"[bold red]System: Tool denied.[/]"))
            # Add a "denial" result as a ToolMessage to history so the model knows it was blocked
            denial_msg = ToolMessage(
                content=f"Error: Tool execution denied by user.",
                tool_call_id=tool_id,
                name=tool_name
            )
            self.conversation_history.append(denial_msg)
            # Re-run graph - it will see the error and continue
            self.run_graph("")
                            
    def update_ui(self, func, *args):
        # Textual helper to update UI from worker
        # Since run_graph is an async worker on the main thread (default), we don't need call_from_thread
        # warning: if we move to thread=True, we might need call_from_thread again.
        func(*args)

if __name__ == "__main__":
    app = RecaizadeApp()
    app.run()
