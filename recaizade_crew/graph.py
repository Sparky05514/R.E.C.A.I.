from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.agents import AgentAction, AgentFinish
import operator

from agents import model_manager
import tools as tool_funcs
from config_manager import config
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from logger import log
from schemas import SCHEMA_MAP
from pydantic import ValidationError

class MCPClientManager:
    """Manages a persistent MCP session to avoid startup overhead."""
    _instance = None
    _session = None
    _exit_stack = None

    @classmethod
    async def get_session(cls):
        if cls._session is None:
            log.info("Starting persistent MCP server...")
            import sys
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["mcp_server.py"],
                env=os.environ.copy()
            )
            # We use an ExitStack pattern if this were sync, but for async we need to manage context manually
            # or use a global-ish setup. Simplified for this environment:
            try:
                cls._client_context = stdio_client(server_params)
                read, write = await cls._client_context.__aenter__()
                cls._session = ClientSession(read, write)
                await cls._session.__aenter__()
                await cls._session.initialize()
                log.info("MCP Session initialized.")
            except Exception as e:
                log.error(f"Failed to start MCP session: {e}")
                cls._session = None
        return cls._session

    @classmethod
    async def cleanup(cls):
        if cls._session:
            log.info("Closing MCP session...")
            await cls._session.__aexit__(None, None, None)
            await cls._client_context.__aexit__(None, None, None)
            cls._session = None
            log.info("MCP session closed.")

TOOL_MAP = {
    "read_file": tool_funcs.read_file,
    "write_file": tool_funcs.write_file,
    "list_directory": tool_funcs.list_directory,
    "delete_file": tool_funcs.delete_file,
    "run_command": tool_funcs.run_command,
    "run_python": tool_funcs.run_python,
    "search_in_files": tool_funcs.search_in_files,
    "move_file": tool_funcs.move_file,
    "copy_file": tool_funcs.copy_file,
    "append_to_file": tool_funcs.append_to_file,
    "get_file_info": tool_funcs.get_file_info,
    "get_project_structure": tool_funcs.get_project_structure,
    "analyze_code": tool_funcs.analyze_code,
    "find_references": tool_funcs.find_references,
    "save_memory": tool_funcs.save_memory,
    "recall_memory": tool_funcs.recall_memory,
    "add_to_context": tool_funcs.add_to_context,
    "web_search": tool_funcs.web_search,
    "fetch_url": tool_funcs.fetch_url,
    "read_webpage": tool_funcs.read_webpage
}

def get_tools_for_role(role: str):
    """Returns tool functions assigned to the role from config."""
    config_key = f"{role}_tools"
    tool_names = config.get("behavior", config_key)
    if not tool_names:
        # Fallback for recaizade if not found
        tool_names = config.get("behavior", "recaizade_tools") if role == "recaizade" else []
    
    return [TOOL_MAP[name] for name in tool_names if name in TOOL_MAP]

async def invoke_model_with_fallback(role, input_data, bind_tools_list=None, retries=2):
    """Invokes model with automatic fallback and retry logic."""
    alert_msg = None
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            model = model_manager.get_model(role)
            # Only bind tools if using Gemini and tools are provided
            if model_manager.provider == "gemini" and bind_tools_list:
                model = model.bind_tools(bind_tools_list)
            
            response = await model.ainvoke(input_data)
            return response, alert_msg
            
        except Exception as e:
            last_error = str(e)
            log.warning(f"Model invocation attempt {attempt+1} failed for {role}: {last_error}")
            if attempt < retries:
                await asyncio.sleep(1 * (attempt + 1)) # Exponential backoff
                continue
            
            # If all retries fail on Gemini, attempt fallback
            if model_manager.provider == "gemini":
                reason = "Unknown API Error"
                if "429" in last_error or "quota" in last_error.lower() or "limit" in last_error.lower():
                    reason = "Rate limit exceeded or Quota exhausted"
                elif "401" in last_error or "key" in last_error.lower():
                    reason = "Invalid or expired API Key"
                elif "503" in last_error or "unavailable" in last_error.lower():
                    reason = "Service unavailable"
                
                alert_msg = f"[SYSTEM ALERT] Gemini Failure ({reason}): {last_error}. Switching to Ollama..."
                log.error(alert_msg)
                model_manager.switch_to_ollama()
                
                # Re-try once on Ollama
                try:
                    model = model_manager.get_model(role)
                    response = await model.ainvoke(input_data)
                    return response, alert_msg
                except Exception as e2:
                    log.critical(f"Critical Error: Fallback to Ollama failed: {e2}")
                    return AIMessage(content=f"[SYSTEM ALERT] Critical Error: Fallback to Ollama failed: {e2}"), alert_msg
            else:
                log.critical(f"Ollama failed definitively: {last_error}")
                return AIMessage(content=f"[SYSTEM ALERT] Critical Error: Local model (Ollama) failed: {last_error}"), None

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
    waiting_confirmation: bool
    pending_tool: dict

# Nodes

async def execute_tool_with_confirmation(tool_name, tool_args, tool_id, messages):
    """Executes tool if safe or confirmed. Returns (result, needs_confirmation)."""
    confirmation_level = config.get("behavior", "tool_confirmation")
    # Validation Layer
    if tool_name in SCHEMA_MAP:
        try:
            schema = SCHEMA_MAP[tool_name]
            # Wrap tool_args in the schema to validate
            validated_args = schema(**tool_args).model_dump()
            log.info(f"Schema validation passed for {tool_name}")
            tool_args = validated_args # Use validated/normalized args
        except ValidationError as e:
            error_details = str(e)
            log.error(f"Schema validation FAILED for {tool_name}: {error_details}")
            return f"Error: Tool argument validation failed for '{tool_name}'. Details: {error_details}. Please fix the arguments and try again.", False
    else:
        log.warning(f"No schema found for tool '{tool_name}', skipping validation.")

    use_mcp = config.get("behavior", "use_mcp")
    is_dangerous = tool_name in tool_funcs.DANGEROUS_TOOLS
    
    # Check if we already have an approval for this tool call in the context
    approval_found = False
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and f"APPROVE_TOOL:{tool_name}:{tool_id}" in msg.content:
            approval_found = True
            break
            
    needs_confirm = False
    if confirmation_level == "all":
        needs_confirm = not approval_found
    elif confirmation_level == "dangerous":
        needs_confirm = is_dangerous and not approval_found
    else: # auto
        needs_confirm = False
        
    if needs_confirm:
        return f"CONFIRMATION_REQUIRED:{tool_name}:{tool_id}", True
        
    # Execute
    if use_mcp:
        for attempt in range(2): # 1 retry
            try:
                session = await MCPClientManager.get_session()
                if session:
                    log.info(f"Executing tool {tool_name} via persistent MCP (Attempt {attempt+1})...")
                    result = await session.call_tool(tool_name, tool_args)
                    return str(result.content), False
                else:
                    log.error("MCP Session unavailable.")
            except Exception as e:
                log.error(f"Error executing {tool_name} via MCP: {e}")
                if attempt == 0:
                    log.info("Resetting MCP connection for retry...")
                    await MCPClientManager.cleanup()
                    await asyncio.sleep(1)
                    continue
        log.error(f"MCP failed definitively for {tool_name}, falling back to local tools.")

    if tool_name in TOOL_MAP:
        try:
            # Run sync tool in thread if needed, but here we just call it
            if asyncio.iscoroutinefunction(TOOL_MAP[tool_name]):
                result = await TOOL_MAP[tool_name](**tool_args)
            else:
                result = TOOL_MAP[tool_name](**tool_args)
            return str(result), False
        except Exception as e:
            return f"Error executing {tool_name}: {e}", False
    return f"Error: Tool {tool_name} not found.", False

async def recaizade_node(state: AgentState):
    messages = list(state['messages'])
    role_tools = get_tools_for_role("recaizade")
    system_prompt = model_manager.get_system_prompt("recaizade")
    
    response, alert = await invoke_model_with_fallback("recaizade", [HumanMessage(content=system_prompt)] + messages, bind_tools_list=role_tools)
    
    node_messages = []
    if alert:
        node_messages.append(AIMessage(content=alert))
    node_messages.append(response)
    
    if response.tool_calls:
        tool_outputs = []
        for tool_call in response.tool_calls:
            result, needs_confirm = await execute_tool_with_confirmation(
                tool_call["name"], tool_call["args"], tool_call["id"], state["messages"]
            )
            
            if needs_confirm:
                return {
                    "messages": [response], 
                    "waiting_confirmation": True, 
                    "pending_tool": tool_call,
                    "sender": "Recaizade"
                }
            
            tool_outputs.append(ToolMessage(content=result, tool_call_id=tool_call["id"], name=tool_call["name"]))
        
        return {"messages": node_messages + tool_outputs, "sender": "Recaizade", "waiting_confirmation": False}
        
    return {"messages": node_messages, "sender": "Recaizade", "waiting_confirmation": False}

def router_node(state: AgentState):
    """Initial node to process input, identify tasks, and route to the correct agent."""
    messages = state.get('messages', [])
    if not messages:
        return {"next_node": "recaizade"}
        
    last_msg = messages[-1]
    content = normalize_content(last_msg.content)
    
    # Default routing
    res = {"next_node": "recaizade"}
    
    # 1. Check for /task command
    if isinstance(last_msg, HumanMessage) and content.strip().startswith("/task"):
        res["task_description"] = content.replace("/task", "").strip()
        res["next_node"] = "coder"
        return res
        
    # 2. Check for tool confirmation/results to continue previous flow
    is_continuation = False
    if isinstance(last_msg, ToolMessage):
        is_continuation = True
    elif isinstance(last_msg, HumanMessage) and ("APPROVE_TOOL" in content or "DENY_TOOL" in content):
        is_continuation = True
        
    if is_continuation:
        # Find the agent that was last active
        for i in range(len(messages)-1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage):
                c = normalize_content(msg.content)
                if c.startswith("Coder:"): 
                    res["next_node"] = "coder"
                    break
                elif c.startswith("Reviewer:"): 
                    res["next_node"] = "reviewer"
                    break
                elif c.startswith("Documenter:"): 
                    res["next_node"] = "documenter"
                    break
                elif c.startswith("Executor:"): 
                    res["next_node"] = "executor"
                    break
                # If no prefix, assume Recaizade
                res["next_node"] = "recaizade"
                break
                
    # 3. Maintain task_description if we are in a crew flow
    if not res.get("task_description"):
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                c = normalize_content(m.content)
                if c.strip().startswith("/task"):
                    res["task_description"] = c.replace("/task", "").strip()
                    break
                    
    return res

def route_input(state: AgentState):
    """Dynamic routing logic for the router node."""
    return state.get("next_node", "recaizade")

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

async def coder_node(state: AgentState):
    task = state.get('task_description', '')
    messages = list(state['messages'])
    role_tools = get_tools_for_role("coder")
    
    conversation_context = format_messages_with_senders(messages)
    
    memory_context = ""
    memory_content = tool_funcs.read_file("bot_memory/memory.md")
    if not memory_content.startswith("Error"):
        memory_context = f"\n=== BOT MEMORY ===\n{memory_content}\n"
    
    system_prompt_base = model_manager.get_system_prompt("coder")
    
    system_prompt = f"""{system_prompt_base}

=== CURRENT TASK ===
{task}
{memory_context}
=== CONVERSATION HISTORY ===
{conversation_context}
"""
    
    response, alert = await invoke_model_with_fallback("coder", [HumanMessage(content=system_prompt)], bind_tools_list=role_tools)
    
    node_messages = []
    if alert:
        node_messages.append(AIMessage(content=alert))
    node_messages.append(response)
    
    content = normalize_content(response.content)
    if content and not content.startswith("Coder:"):
        response.content = f"Coder: {content}"
    
    if response.tool_calls:
        tool_outputs = []
        for tool_call in response.tool_calls:
            result, needs_confirm = await execute_tool_with_confirmation(
                tool_call["name"], tool_call["args"], tool_call["id"], state["messages"]
            )
            
            if needs_confirm:
                return {
                    "messages": [response], 
                    "waiting_confirmation": True, 
                    "pending_tool": tool_call,
                    "sender": "Coder"
                }
            
            tool_outputs.append(ToolMessage(content=result, tool_call_id=tool_call["id"], name=tool_call["name"]))
        
        return {"messages": node_messages + tool_outputs, "sender": "Coder", "waiting_confirmation": False}
        
    return {"messages": node_messages, "sender": "Coder", "waiting_confirmation": False}

async def executor_node(state: AgentState):
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
        last_backticks = code_block_raw.rfind('```')
        if last_backticks <= first_newline: continue
        
        code = code_block_raw[first_newline+1 : last_backticks]
        
        # IMPROVED PARSING: More flexible regex to find the filename
        # 1. Look for explicit File label in preceding text
        # 2. Look for filename-like pattern in the last line of preceding text
        # 3. Look for comment header inside the code block
        
        filename = None
        
        # Strategy 1: Explicit Label
        file_matches = list(re.finditer(r"(?:File|Filename|Path):\s*[`'\"]?([\w\./_\-]+)[`'\"]?", preceding_text, re.IGNORECASE))
        if file_matches:
            filename = file_matches[-1].group(1).strip()
        
        # Strategy 2: Last line of preceding text (if it looks like a path)
        if not filename:
             lines = preceding_text.strip().split('\n')
             if lines:
                 last_line = lines[-1].strip()
                 # Match something that looks like 'path/to/file.ext' or similar
                 path_match = re.search(r"([\w_\-\.]+/)*[\w_\-\.]+\.\w+", last_line)
                 if path_match:
                     filename = path_match.group(0).strip()

        # Strategy 3: Comment header inside code
        if not filename:
            first_line = code.split('\n')[0].strip()
            comment_match = re.search(r"(?:File|Filename|Path):\s*[`'\"]?([\w\./_\-]+)[`'\"]?", first_line, re.IGNORECASE)
            if comment_match:
                filename = comment_match.group(1).strip()

        if filename:
            # Basic validation: ensure it's not too long and has an extension
            if len(filename) < 100 and '.' in filename:
                result = tool_funcs.write_file(filename, code)
                executed_files.append(f"  - {filename}: {result}")
            else:
                executed_files.append(f"  - [Skipped]: Identified suspicious filename '{filename}'")
        else:
             executed_files.append(f"  - [Skipped]: Found code block but no valid filename identified.")

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

async def reviewer_node(state: AgentState):
    messages = list(state['messages'])
    role_tools = get_tools_for_role("reviewer")
    task = state.get('task_description', 'No task description available')
    conversation_context = format_messages_with_senders(messages)
    system_prompt_base = model_manager.get_system_prompt("reviewer")
    
    prompt = f"""{system_prompt_base}
=== ORIGINAL TASK ===
{task}
=== CONVERSATION HISTORY ===
{conversation_context}
"""
    
    response, alert = await invoke_model_with_fallback("reviewer", [HumanMessage(content=prompt)], bind_tools_list=role_tools)
    
    node_messages = []
    if alert:
        node_messages.append(AIMessage(content=alert))
    node_messages.append(response)
    
    content = normalize_content(response.content)
    if content and not content.startswith("Reviewer:"):
        response.content = f"Reviewer: {content}"
            
    if response.tool_calls:
        tool_outputs = []
        for tool_call in response.tool_calls:
            result, needs_confirm = await execute_tool_with_confirmation(
                tool_call["name"], tool_call["args"], tool_call["id"], state["messages"]
            )
            
            if needs_confirm:
                return {
                    "messages": [response], 
                    "waiting_confirmation": True, 
                    "pending_tool": tool_call,
                    "sender": "Reviewer"
                }
            
            tool_outputs.append(ToolMessage(content=result, tool_call_id=tool_call["id"], name=tool_call["name"]))
        
        node_messages = node_messages + tool_outputs
    else:
        node_messages = node_messages

    last_content = normalize_content(node_messages[-1].content)
    status = "APPROVED" if "REVIEW_PASSED" in last_content.upper() else "REJECTED"
    
    return {"messages": node_messages, "sender": "Reviewer", "review_status": status, "waiting_confirmation": False}

async def documenter_node(state: AgentState):
    messages = list(state['messages'])
    role_tools = get_tools_for_role("documenter")
    task = state.get('task_description', '')
    review_status = state.get('review_status', 'UNKNOWN')
    conversation_context = format_messages_with_senders(messages)
    system_prompt_base = model_manager.get_system_prompt("documenter")
    
    prompt = f"""{system_prompt_base}
=== CURRENT TASK ===
{task}
=== REVIEW STATUS ===
{review_status}
=== CONVERSATION HISTORY ===
{conversation_context}
"""
    
    response, alert = await invoke_model_with_fallback("documenter", [HumanMessage(content=prompt)], bind_tools_list=role_tools)
    
    node_messages = []
    if alert:
        node_messages.append(AIMessage(content=alert))
    node_messages.append(response)
    
    content = normalize_content(response.content)
    if content and not content.startswith("Documenter:"):
        response.content = f"Documenter: {content}"
            
    if response.tool_calls:
        tool_outputs = []
        for tool_call in response.tool_calls:
            result, needs_confirm = await execute_tool_with_confirmation(
                tool_call["name"], tool_call["args"], tool_call["id"], state["messages"]
            )
            
            if needs_confirm:
                return {
                    "messages": [response], 
                    "waiting_confirmation": True, 
                    "pending_tool": tool_call,
                    "sender": "Documenter"
                }
            
            tool_outputs.append(ToolMessage(content=result, tool_call_id=tool_call["id"], name=tool_call["name"]))
        node_messages = node_messages + tool_outputs
    else:
        node_messages = node_messages

    final_content = normalize_content(node_messages[-1].content)
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    user_report = ""
    bot_memory = ""
    import re
    user_match = re.search(r"User Report:(.*?)(?=Bot Memory:|$)", final_content, re.DOTALL | re.IGNORECASE)
    if user_match: user_report = user_match.group(1).strip()
    memory_match = re.search(r"Bot Memory:(.*?)(?=$)", final_content, re.DOTALL | re.IGNORECASE)
    if memory_match: bot_memory = memory_match.group(1).strip()
        
    if user_report:
        tool_funcs.write_file(f"user_reports/report_{timestamp}.md", f"# Progress Report - {timestamp}\n\n{user_report}")
    if bot_memory:
        tool_funcs.write_file("bot_memory/memory.md", bot_memory)
        tool_funcs.write_file(f"bot_memory/memory_{timestamp}.md", bot_memory)
        
    return {"messages": node_messages, "sender": "Documenter", "waiting_confirmation": False}

# Building the Graph
workflow = StateGraph(AgentState)

workflow.add_node("recaizade", recaizade_node)
workflow.add_node("coder", coder_node)
workflow.add_node("executor", executor_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("documenter", documenter_node)

workflow.add_node("router", router_node)

workflow.set_entry_point("router")

workflow.add_conditional_edges(
    "router",
    route_input,
    {
        "coder": "coder",
        "recaizade": "recaizade",
        "executor": "executor",
        "reviewer": "reviewer",
        "documenter": "documenter"
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
    # Also check if there was a systemic failure (don't loop if models are failing)
    messages = state.get('messages', [])
    if messages:
        last_msg = messages[-1]
        content = normalize_content(last_msg.content)
        if "[SYSTEM ALERT]" in content:
            return "end"

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
