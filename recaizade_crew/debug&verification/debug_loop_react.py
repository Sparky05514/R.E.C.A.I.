from agents import model_manager
from tools import read_file, write_file, list_directory, delete_file
from langchain_core.messages import HumanMessage
from graph import recaizade_node, AgentState

# Force switch to Ollama
print("Manually switching to Ollama...")
model_manager.switch_to_ollama()

# Create dummy state
state = AgentState(
    messages=[HumanMessage(content="List the files in the current directory.")],
    next_node="",
    task_description="",
    code_content="",
    review_status=""
)

print("Invoking Recaizade (Ollama) with ReAct loop...")
try:
    result = recaizade_node(state)
    
    print("\n--- RESPONSE ANALYSIS ---")
    messages = result['messages']
    print(f"Total Messages Returned: {len(messages)}")
    
    for i, msg in enumerate(messages):
        content = msg.content
        if isinstance(content, list):
             content = "".join([str(item.get("text", "")) for item in content if item.get("type") == "text"])
        
        print(f"\n[Message {i}] Sender: {result.get('sender')}")
        print(f"Content: '{content}'")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"Tool Calls: {msg.tool_calls}")
            
    # Check for desired flow
    first_msg_content = messages[0].content
    if isinstance(first_msg_content, list):
        first_msg_content = "".join([str(item.get("text", "")) for item in first_msg_content if item.get("type") == "text"])
        
    if "<thinking>" in first_msg_content:
        print("\n[SUCCESS]: Found <thinking> tags.")
    else:
        print("\n[WARNING]: No <thinking> tags found in first message.")
        
    if len(messages) >= 2: # At least Tool Call + Tool Result + Follow up hopefully?
         print("\n[Observation]: Multiple messages indicate loop execution.")
    else:
         print("\n[Observation]: Single message returned. Did it loop?")

except Exception as e:
    print(f"\n[ERROR] Invocation failed: {e}")
    import traceback
    traceback.print_exc()
