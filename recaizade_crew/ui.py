from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Log, Static
from textual.containers import Container, Vertical, Horizontal
from textual import work
from rich.text import Text
from langchain_core.messages import HumanMessage, AIMessage

from graph import app_graph

class ChatMessage(Static):
    def __init__(self, message, sender, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.sender = sender

    def compose(self) -> ComposeResult:
        # Style based on sender
        color = "green" if self.sender == "User" else "blue"
        if self.sender == "Recaizade":
            color = "cyan"
        elif self.sender in ["Coder", "Executor", "Reviewer"]:
            color = "magenta"
        
        yield Static(f"[{color}]{self.sender}:[/{color}] {self.message}")

class RecaizadeApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-columns: 3fr 1fr;
    }
    
    #chat-container {
        height: 100%;
        border: solid green;
    }
    
    #log-container {
        height: 100%;
        border: solid yellow;
    }
    
    #input-box {
        dock: bottom;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="chat-container"):
            yield Log(id="chat-log")
        
        with Container(id="log-container"):
            yield Log(id="debug-log")

        yield Input(placeholder="Talk to Recaizade...", id="input-box")
        yield Header()
        yield Footer()

    def on_mount(self):
        self.title = "Recaizade Crew"
        self.chat_log = self.query_one("#chat-log", Log)
        self.debug_log = self.query_one("#debug-log", Log)
        
        # Initialize graph state if needed, or just keep history in memory locally
        self.conversation_history = []
        
        self.chat_log.write("[bold green]System: Welcome to Recaizade Crew![/]")

    async def on_input_submitted(self, message: Input.Submitted):
        user_input = message.value
        message.input.value = ""
        
        if not user_input.strip():
            return

        self.chat_log.write(f"[bold green]User:[/] {user_input}")
        
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
                self.update_ui(self.debug_log.write, f"Step: {key}")
                if "messages" in value:
                    new_messages = value["messages"]
                    # If this is a list of new messages, we display them.
                    # Since we use operator.add, the output of the node is just the new messages usually.
                    for msg in new_messages:
                        sender = "Unknown"
                        content = msg.content
                        
                        if key == "recaizade":
                            sender = "Recaizade"
                        elif key == "coder":
                            sender = "Coder"
                        elif key == "executor":
                            sender = "Executor"
                        elif key == "reviewer":
                            sender = "Reviewer"
                        
                        # Update main chat window
                        self.update_ui(self.chat_log.write, f"[bold cyan]{sender}:[/] {content}")
                        
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
        self.call_from_thread(func, *args)

if __name__ == "__main__":
    app = RecaizadeApp()
    app.run()
