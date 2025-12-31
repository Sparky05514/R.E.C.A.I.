from agents import model_manager
from tools import read_file, write_file, list_directory, delete_file
from langchain_core.messages import HumanMessage, AIMessage

# Force switch to Ollama for debugging
print("Manually switching to Ollama...")
model_manager.switch_to_ollama()

# Get Recaizade model
try:
    recaizade = model_manager.get_model("recaizade")
except Exception as e:
    print(f"Error getting model: {e}")
    exit(1)

# Bind tools
tools = [read_file, write_file, list_directory, delete_file]
recaizade_with_tools = recaizade.bind_tools(tools)

print("Invoking Recaizade (Ollama) with a tool-heavy request...")
prompt = "List the files in the current directory and read the README.md if it exists."

try:
    response = recaizade_with_tools.invoke([HumanMessage(content=prompt)])
    
    print("\n--- RESPONSE ANALYSIS ---")
    print(f"Content: '{response.content}'")
    print(f"Tool Calls: {response.tool_calls}")
    
    if response.tool_calls and not response.content:
        print("\n[HYPOTHESIS CONFIRMED]: Model returns ONLY tool calls with NO text content.")
        print("In current graph logic, this results in the user seeing only the tool output.")
        print("If the user replies, the model might see tool output and just call another tool?")
    elif response.tool_calls and response.content:
        print("\n[Observation]: Model returns both content and tool calls.")
    else:
        print("\n[Observation]: Model returned text only (or nothing).")

except Exception as e:
    print(f"\n[ERROR] Invocation failed: {e}")
