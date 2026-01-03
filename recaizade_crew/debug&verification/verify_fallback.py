from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage

# Mock imports before loading agents/graph
import sys
from unittest.mock import patch

print("Setting up verification...")

# Import agents and graph
# We need to use real imports but patch the model invocation
from agents import model_manager
from graph import recaizade_node, AgentState

# Mock state
state = {
    "messages": [HumanMessage(content="Hello Recaizade")],
    "task_description": "",
    "review_status": ""
}

print(f"Initial provider: {model_manager.provider} (Expected: gemini)")

# Mock Gemini failure
original_gemini = model_manager.models['recaizade']
model_manager.models['recaizade'] = MagicMock()
model_manager.models['recaizade'].invoke.side_effect = Exception("Quota exceeded")
# bind_tools also needs to be mocked to return the mock that raises
model_manager.models['recaizade'].bind_tools.return_value = model_manager.models['recaizade']

print("Simulating Gemini failure...")

# Run node
result = recaizade_node(state)

print(f"Final provider: {model_manager.provider}")
print(f"Messages returned: {len(result['messages'])}")
first_msg_content = result['messages'][0].content
print(f"First message (Alert?): {first_msg_content}")

if model_manager.provider == "ollama" and "[SYSTEM ALERT]" in str(first_msg_content):
    print("SUCCESS: Fallback to Ollama verified.")
else:
    print("FAILURE: Fallback did not occur as expected.")
