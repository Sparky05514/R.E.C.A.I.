import asyncio
from graph import app_graph
from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.panel import Panel

async def test_antigravity_flow():
    console = Console()
    console.print("[bold green]Starting Antigravity Flow Integration Test...[/]")
    
    # Simple prompt that triggers a tool (list_directory)
    initial_state = {
        "messages": [HumanMessage(content="Hello! Can you list the files in the current directory and tell me what you see?")],
        "next_node": "",
        "task_description": "",
        "code_content": "",
        "review_status": ""
    }

    console.print(Panel("Prompt: List the files in the current directory.", title="User Request"))

    async for event in app_graph.astream(initial_state):
        for node_name, value in event.items():
            console.print(f"\n[bold yellow]Node: {node_name}[/]")
            if "messages" in value:
                for msg in value["messages"]:
                    content = getattr(msg, 'content', str(msg))
                    if isinstance(content, list):
                        content = "".join([item.get("text", "") for item in content if item.get("type") == "text"])
                    
                    if "<thinking>" in content:
                        console.print(f"[dim italic]Thinking detected in output.[/]")
                    
                    # Check for tool calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        console.print(f"[bold blue]Tool Call:[/] {msg.tool_calls[0].get('name')}")
                    elif msg.__class__.__name__ == 'ToolMessage':
                        console.print(f"[bold green]Tool Result:[/] {str(content)[:100]}...")
                    else:
                        console.print(f"[bold cyan]Response:[/]\n{content}")

    console.print("\n[bold green]Test Complete.[/]")

if __name__ == "__main__":
    asyncio.run(test_antigravity_flow())
