from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.containers import Container, Vertical, Horizontal
from textual import work
from rich.text import Text
from rich.markup import escape
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from graph import app_graph

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
    """

    def compose(self) -> ComposeResult:
        with Container(id="chat-container"):
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
        
        with Container(id="log-container"):
            yield RichLog(id="debug-log", highlight=True, markup=True, wrap=True)

        yield Input(placeholder="Talk to Recaizade...", id="input-box")
        yield Header()
        yield Footer()

    def on_mount(self):
        self.title = "Recaizade Crew"
        self.chat_log = self.query_one("#chat-log", RichLog)
        self.debug_log = self.query_one("#debug-log", RichLog)
        
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
