from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.agents import AgentAction, AgentFinish
import operator

from agents import recaizade_model, crew_model, RECAIZADE_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, EXECUTOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT
from tools import read_file, write_file, list_directory, delete_file

# Define tools list for the agents to know about (even if we manually invoke them or bind them)
tools = [read_file, write_file, list_directory, delete_file]
# For Gemini, we might need to bind tools if we want function calling.
# For this simplified version, let's use prompt engineering + manual parsing or simple function calling if generic enough.
# Let's bind tools to the executor model.
crew_model_with_tools = crew_model.bind_tools(tools)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_node: str
    task_description: str
    code_content: str
    review_status: str

# Nodes

def recaizade_node(state: AgentState):
    messages = state['messages']
    # Add system prompt if not present at the start of valid interaction (simplified here)
    # We just send the conversation to Recaizade
    response = recaizade_model.invoke([HumanMessage(content=RECAIZADE_SYSTEM_PROMPT)] + messages)
    return {"messages": [response], "sender": "Recaizade"}

def router(state: AgentState):
    # Check the last message. If it starts with /task, route to crew.
    last_msg = state['messages'][-1]
    if isinstance(last_msg, HumanMessage) and last_msg.content.strip().startswith("/task"):
        # Extract task
        task = last_msg.content.replace("/task", "").strip()
        # Initialize task description
        return {"next_node": "coder", "task_description": task}
    elif isinstance(last_msg, AIMessage) and "crew" in last_msg.content.lower() and "start" in last_msg.content.lower():
         # Maybe Recaizade triggered it? For now, let's stick to user explicit command or Recaizade calling a tool.
         pass
    return {"next_node": "end"}

def coder_node(state: AgentState):
    task = state.get('task_description', '')
    messages = state['messages']
    # Filter messages to just relevant context if needed, or keeping history is fine.
    # We prompt Coder
    prompt = f"{CODER_SYSTEM_PROMPT}\nTask: {task}\nCurrent conversation history provided."
    response = crew_model.invoke([HumanMessage(content=prompt)] + messages)
    return {"messages": [response], "sender": "Coder"}

def executor_node(state: AgentState):
    # Executor should look at the last message from Coder and execute tools?
    # Or simplified: Coder just writes code blocks, Executor applies them?
    # Better: Coder uses 'write_file' tool calls directly?
    # Let's try to let the crew_model_with_tools handle it.
    
    last_msg = state['messages'][-1]
    # In a real agent loop, we'd process tool calls.
    # For this graph, let's assume Coder outputs text, Executor interprets and acts.
    # Or we make Coder capable of tool calls.
    
    # Let's use the 'crew_model_with_tools' for the Coder actually, so Coder can write files directly.
    # But the requirement split them.
    # Let's say Executor takes the code from Coder and writes it.
    
    code_content = last_msg.content
    # Simple heuristic: extract code block
    import re
    code_match = re.search(r"```python(.*?)```", code_content, re.DOTALL)
    if code_match:
        code = code_match.group(1).strip()
        # We need a filename.
        # Let's ask the Coder to specify filename in a structured way or just regex it.
        # "File: filename.py"
        file_match = re.search(r"File:\s*([\w\./]+)", code_content)
        if file_match:
            filename = file_match.group(1).strip()
            result = write_file(filename, code)
            return {"messages": [AIMessage(content=f"Executor: Wrote file {filename}. Result: {result}")], "sender": "Executor"}
    
    # If no code block, maybe just a message
    return {"messages": [AIMessage(content="Executor: No code block or filename found to execute.")], "sender": "Executor"}

def reviewer_node(state: AgentState):
    messages = state['messages']
    last_msg = messages[-1]
    prompt = f"{REVIEWER_SYSTEM_PROMPT}\nReview the actions taken: {last_msg.content}"
    response = crew_model.invoke([HumanMessage(content=prompt)])
    
    status = "APPROVED" if "APPROVED" in response.content else "REJECTED"
    return {"messages": [response], "sender": "Reviewer", "review_status": status}

# Building the Graph
workflow = StateGraph(AgentState)

workflow.add_node("recaizade", recaizade_node)
workflow.add_node("coder", coder_node)
workflow.add_node("executor", executor_node)
workflow.add_node("reviewer", reviewer_node)

# We need a custom entrypoint logic or just start at recaizade usually.
# But for /task, we might intercept before Recaizade?
# Let's say the TUI sends the message to the graph.

def route_start(state: AgentState):
    # If last message is /task, go to Coder (start crew)
    # Else go to Recaizade
    last_msg = state['messages'][-1]
    if isinstance(last_msg, HumanMessage) and last_msg.content.strip().startswith("/task"):
        return "coder"
    return "recaizade"

workflow.set_conditional_entry_point(
    route_start,
    {
        "coder": "coder",
        "recaizade": "recaizade"
    }
)

# Recaizade just replies and ends
workflow.add_edge("recaizade", END)

# Crew Loop
workflow.add_edge("coder", "executor")
workflow.add_edge("executor", "reviewer")

def route_review(state: AgentState):
    if state.get("review_status") == "APPROVED":
        return "end"
    else:
        return "coder" # Loop back to fix

workflow.add_conditional_edges(
    "reviewer",
    route_review,
    {
        "end": END,
        "coder": "coder"
    }
)

app_graph = workflow.compile()
