from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.agents import AgentAction, AgentFinish
import operator

from agents import model_manager, RECAIZADE_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, EXECUTOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT, DOCUMENTER_SYSTEM_PROMPT
from tools import read_file, write_file, list_directory, delete_file

# Define tools list for the agents to know about (even if we manually invoke them or bind them)
tools = [read_file, write_file, list_directory, delete_file]

def invoke_model_with_fallback(role, input_data, bind_tools_list=None):
    """Invokes model with automatic fallback to Ollama on failure. Returns (response, alert_message)."""
    try:
        model = model_manager.get_model(role)
        if bind_tools_list:
            model = model.bind_tools(bind_tools_list)
        return model.invoke(input_data), None
    except Exception as e:
        alert_msg = f"[SYSTEM ALERT] API Error: {e}. Switching to Ollama..."
        print(alert_msg) # Keep print for fallback logging
        model_manager.switch_to_ollama()
        
        # Retry with new provider
        model = model_manager.get_model(role)
        if bind_tools_list:
            model = model.bind_tools(bind_tools_list)
        return model.invoke(input_data), alert_msg

def normalize_content(content):
    """Normalize message content to string if it is a list (multimodal response)."""
    if content is None:
        return ""
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
    messages = list(state['messages']) # Make a copy to mutate locally
    
    # ReAct Loop
    MAX_ITERATIONS = 3
    iterations = 0
    final_alert = None
    
    while iterations < MAX_ITERATIONS:
        # Invoke model
        # For the first iteration, messages are just the state messages.
        # For subsequent iterations, messages include the previous AIMessage (with tool calls) and ToolMessages.
        response, alert = invoke_model_with_fallback("recaizade", [HumanMessage(content=RECAIZADE_SYSTEM_PROMPT)] + messages, bind_tools_list=tools)
        if alert:
            final_alert = alert # Keep the latest alert if any
            
        # Append response to local history
        messages.append(response)
        
        # Check for tool calls
        if not response.tool_calls:
            # No tool calls, we have a final response
            break
            
        # Execute Tools
        tool_outputs = []
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
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
            
            # Create ToolMessage
            tool_outputs.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_id,
                name=tool_name
            ))
            
        # Append tool outputs to local history
        messages.extend(tool_outputs)
        iterations += 1
    
    # Final response processing
    # If we exited the loop because of MAX_ITERATIONS and still have tool calls, we might want to warn.
    # But usually the last response will be the text response if break occurred.
    
    # We want to return just the NEW messages generated during this node's execution (including tool calls and results, and final response)
    # The state['messages'] has the original history. 'messages' has everything.
    # Diff them? Or simplier: the 'messages' agent state annotation uses operator.add.
    # So we just return the new messages appended.
    
    new_messages = messages[len(state['messages']):]
    
    # We also need to normalize content for the final AI message if needed, 
    # but the loop handles the structure.
    # The only thing is normalizing for the 'sender' check or logging if we want.
    # For now, we trust the model's final response is text.
    
    if final_alert:
        new_messages.insert(0, AIMessage(content=final_alert))
        
    return {"messages": new_messages, "sender": "Recaizade"}

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
    
    # Read Bot Memory if it exists
    memory_context = ""
    memory_content = read_file("bot_memory/memory.md")
    if not memory_content.startswith("Error"):
        memory_context = f"\n=== BOT MEMORY (Recent History & Context) ===\n{memory_content}\n"
    
    # Build a comprehensive prompt with crew awareness
    prompt = f"""{CODER_SYSTEM_PROMPT}

=== CREW CONTEXT ===
You are part of a crew with:
- Executor: Will implement your code by writing files
- Reviewer: Will review the implementation and approve or request changes
- Documenter: Reviews progress and maintains memory

=== CURRENT TASK ===
{task}
{memory_context}
=== CONVERSATION HISTORY ===
{conversation_context}

=== YOUR RESPONSE ===
Provide your code solution. Include "File: filename.py" before code blocks so Executor knows where to write.
Start your response with "Coder:" to identify yourself.
"""
    
    response, alert = invoke_model_with_fallback("coder", [HumanMessage(content=prompt)])
    content = normalize_content(response.content)
    
    # Ensure response is prefixed with sender identity
    if not content.startswith("Coder:"):
        content = f"Coder: {content}"
    
    out_messages = [AIMessage(content=content)]
    if alert:
        out_messages.insert(0, AIMessage(content=alert))
        
    return {"messages": out_messages, "sender": "Coder"}

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
    
    response, alert = invoke_model_with_fallback("reviewer", [HumanMessage(content=prompt)])
    content = normalize_content(response.content)
    
    # Ensure response is prefixed with sender identity
    if not content.startswith("Reviewer:"):
        content = f"Reviewer: {content}"
    
    
    status = "APPROVED" if "APPROVED" in content.upper() else "REJECTED"
    
    out_messages = [AIMessage(content=content)]
    if alert:
        out_messages.insert(0, AIMessage(content=alert))
        
    return {"messages": out_messages, "sender": "Reviewer", "review_status": status}

def documenter_node(state: AgentState):
    """Documenter creates reports for user and memory for bots."""
    messages = state['messages']
    task = state.get('task_description', '')
    review_status = state.get('review_status', 'UNKNOWN')
    
    # Format context
    conversation_context = format_messages_with_senders(messages)
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    prompt = f"""{DOCUMENTER_SYSTEM_PROMPT}

=== CURRENT TASK ===
{task}

=== REVIEW STATUS ===
{review_status}

=== FULL CONVERSATION ===
{conversation_context}

=== INSTRUCTIONS ===
1. Analyze the conversation and actions taken.
2. Generate a User Report (User Report: ...)
3. Generate a Bot Memory (Bot Memory: ...)

Start your response with "Documenter:".
"""
    response, alert = invoke_model_with_fallback("documenter", [HumanMessage(content=prompt)])
    content = normalize_content(response.content)
    if not content.startswith("Documenter:"):
        content = f"Documenter: {content}"
        
    # Extract and write files
    # We look for sections or just dump the whole thing?
    # Better to parse if possible, or just append to log.
    
    # Simple parsing strategy:
    user_report = ""
    bot_memory = ""
    
    import re
    user_match = re.search(r"User Report:(.*?)(?=Bot Memory:|$)", content, re.DOTALL | re.IGNORECASE)
    if user_match:
        user_report = user_match.group(1).strip()
        
    memory_match = re.search(r"Bot Memory:(.*?)(?=$)", content, re.DOTALL | re.IGNORECASE)
    if memory_match:
        bot_memory = memory_match.group(1).strip()
        
    if user_report:
        write_file(f"user_reports/report_{timestamp}.md", f"# Progress Report - {timestamp}\n\n{user_report}")
        
    if bot_memory:
        # Append to memory file or overwrite? User said: "bots will read the latest things and remember"
        # Overwrite seems better for "state", appending for "log". 
        # "remember about the important things" -> implies cumulative state or latest summary.
        # Let's overwrite 'memory.md' with the latest comprehensive memory state.
        write_file("bot_memory/memory.md", bot_memory)
        # Also keep a history?
        write_file(f"bot_memory/memory_{timestamp}.md", bot_memory)
        
    out_messages = [AIMessage(content=content)]
    if alert:
        out_messages.insert(0, AIMessage(content=alert))
        
    return {"messages": out_messages, "sender": "Documenter"}

# Building the Graph
workflow = StateGraph(AgentState)

workflow.add_node("recaizade", recaizade_node)
workflow.add_node("coder", coder_node)
workflow.add_node("executor", executor_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("documenter", documenter_node)

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
workflow.add_edge("reviewer", "documenter") # Reviewer -> Documenter

def route_documenter(state: AgentState):
    # After documentation, check if we are done based on reviewer status
    if state.get("review_status") == "APPROVED":
        return "end"
    else:
        return "coder" # Loop back to fix

workflow.add_conditional_edges(
    "documenter",
    route_documenter,
    {
        "end": END,
        "coder": "coder"
    }
)

app_graph = workflow.compile()
