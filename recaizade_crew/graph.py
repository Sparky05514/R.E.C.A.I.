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
# Let's bind tools to models.
recaizade_model_with_tools = recaizade_model.bind_tools(tools)
crew_model_with_tools = crew_model.bind_tools(tools)

def normalize_content(content):
    """Normalize message content to string if it is a list (multimodal response)."""
    if isinstance(content, list):
        return "".join([str(item.get("text", "")) for item in content if item.get("type") == "text"])
    return str(content)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_node: str
    task_description: str
    code_content: str
    review_status: str

# Nodes

def recaizade_node(state: AgentState):
    messages = state['messages']
    # Filter messages for a cleaner context if needed, but here we pass all.
    # We use the model with tools.
    response = recaizade_model_with_tools.invoke([HumanMessage(content=RECAIZADE_SYSTEM_PROMPT)] + messages)
    
    # Handle Tool Calls
    if response.tool_calls:
        # For simplicity in this graph structure, we execute them immediately and return the result as a message.
        # In a more robust graph, we'd have a 'tools' node.
        tool_results = []
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # Simple manual routing of tool calls
            if tool_name == "read_file":
                result = read_file(**tool_args)
            elif tool_name == "write_file":
                result = write_file(**tool_args)
            elif tool_name == "list_directory":
                result = list_directory(**tool_args)
            elif tool_name == "delete_file":
                result = delete_file(**tool_args)
            else:
                result = f"Error: Tool {tool_name} not found."
            
            tool_results.append(f"Tool '{tool_name}' result: {result}")
        
        # We append a summary of tool actions to the AI content or as a separate message
        combined_content = normalize_content(response.content) + "\n\n" + "\n".join(tool_results)
        response.content = combined_content
    else:
        response.content = normalize_content(response.content)
        
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

def format_messages_with_senders(messages):
    """Format messages with sender attribution for crew context."""
    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted.append(f"[User]: {normalize_content(msg.content)}")
        elif isinstance(msg, AIMessage):
            # Try to identify sender from content patterns or default to previous context
            content = normalize_content(msg.content)
            if content.startswith("Executor:"):
                formatted.append(f"[Executor]: {content}")
            elif content.startswith("Coder:"):
                formatted.append(f"[Coder]: {content}")
            elif content.startswith("Reviewer:"):
                formatted.append(f"[Reviewer]: {content}")
            else:
                formatted.append(f"[Recaizade]: {content}")
    return "\n\n".join(formatted)

def coder_node(state: AgentState):
    task = state.get('task_description', '')
    messages = state['messages']
    
    # Format conversation history with sender attribution
    conversation_context = format_messages_with_senders(messages)
    
    # Build a comprehensive prompt with crew awareness
    prompt = f"""{CODER_SYSTEM_PROMPT}

=== CREW CONTEXT ===
You are part of a crew with:
- Executor: Will implement your code by writing files
- Reviewer: Will review the implementation and approve or request changes

=== CURRENT TASK ===
{task}

=== CONVERSATION HISTORY ===
{conversation_context}

=== YOUR RESPONSE ===
Provide your code solution. Include "File: filename.py" before code blocks so Executor knows where to write.
Start your response with "Coder:" to identify yourself.
"""
    
    response = crew_model.invoke([HumanMessage(content=prompt)])
    content = normalize_content(response.content)
    
    # Ensure response is prefixed with sender identity
    if not content.startswith("Coder:"):
        content = f"Coder: {content}"
    
    return {"messages": [AIMessage(content=content)], "sender": "Coder"}

def executor_node(state: AgentState):
    """Executor takes the Coder's output and implements it by writing files."""
    import re
    
    messages = state['messages']
    last_msg = messages[-1]
    
    # Get conversation context for better understanding
    conversation_context = format_messages_with_senders(messages)
    
    code_content = normalize_content(last_msg.content)
    
    executed_files = []
    
    # Robust parsing: Split content by code blocks to find preceding filenames
    # This handles interleaved text and code correctly
    parts = re.split(r"(```(?:\w+)?\n.*?```)", code_content, flags=re.DOTALL)
    
    found_code = False
    
    # Parts will be [text, code_block, text, code_block...]
    # We iterate over code blocks (indices 1, 3, 5...)
    for i in range(1, len(parts), 2):
        code_block_raw = parts[i]
        preceding_text = parts[i-1]
        found_code = True
        
        # Extract code content (strip backticks)
        # Find first newline
        first_newline = code_block_raw.find('\n')
        if first_newline == -1: continue
        
        # End is usually the last 3 chars ``` (or more backticks)
        # We can just look for the last ```
        last_backticks = code_block_raw.rfind('```')
        if last_backticks <= first_newline: continue
        
        code = code_block_raw[first_newline+1 : last_backticks]
        
        # Find filename in preceding text (look for last occurrence)
        file_matches = list(re.finditer(r"(?:File|Filename):\s*[`'\"]?([\w\./_\-]+)[`'\"]?", preceding_text, re.IGNORECASE))
        
        if file_matches:
            filename = file_matches[-1].group(1).strip()
            result = write_file(filename, code)
            executed_files.append(f"  - {filename}: {result}")
        else:
             # Try to find it in the first line of the code block if it was a comment?
             # Or just report missing filename
             executed_files.append(f"  - [Skipped]: Found code block but no 'File: filename.py' specified before it.")

    if executed_files:
        files_summary = "\n".join(executed_files)
        response_content = f"""Executor: I have implemented the Coder's solution.

Files processed:
{files_summary}

Reviewer, please review these changes and verify they meet the requirements from the original task."""
    else:
        # No code found - communicate this to the crew
        if found_code:
             response_content = f"""Executor: I found code blocks but couldn't associate them with filenames.
Please ensure you write "File: filename.py" immediately before each code block."""
        else:
            response_content = f"""Executor: I could not find properly formatted code blocks to execute.

Coder, please ensure your response includes:
1. "File: filename.py" before each code block
2. Code wrapped in ```python ... ``` blocks

I'll wait for updated instructions."""
    
    return {"messages": [AIMessage(content=response_content)], "sender": "Executor"}

def reviewer_node(state: AgentState):
    """Reviewer evaluates the work done by Coder and Executor."""
    messages = state['messages']
    task = state.get('task_description', 'No task description available')
    
    # Format full conversation for context
    conversation_context = format_messages_with_senders(messages)
    
    prompt = f"""{REVIEWER_SYSTEM_PROMPT}

=== CREW CONTEXT ===
You are part of a crew with:
- Coder: Wrote the code solution
- Executor: Implemented the code by writing files
You are reviewing their work.

=== ORIGINAL TASK ===
{task}

=== FULL CONVERSATION ===
{conversation_context}

=== YOUR REVIEW ===
Review the implementation against the original task requirements.
If the work meets requirements, respond with "APPROVED" and explain why.
If changes are needed, provide specific feedback to the Coder about what to fix.
Start your response with "Reviewer:" to identify yourself.
"""
    
    response = crew_model.invoke([HumanMessage(content=prompt)])
    content = normalize_content(response.content)
    
    # Ensure response is prefixed with sender identity
    if not content.startswith("Reviewer:"):
        content = f"Reviewer: {content}"
    
    status = "APPROVED" if "APPROVED" in content.upper() else "REJECTED"
    return {"messages": [AIMessage(content=content)], "sender": "Reviewer", "review_status": status}

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
