from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import sys

# Mock imports
sys.modules['agents'] = MagicMock()
sys.modules['tools'] = MagicMock()

# Mock specific functions/objects
mock_read_file = MagicMock(return_value="File content")
sys.modules['tools'].read_file = mock_read_file
sys.modules['tools'].write_file = MagicMock()
sys.modules['tools'].list_directory = MagicMock()
sys.modules['tools'].delete_file = MagicMock()

# Import graph after mocking
with patch('graph.model_manager') as mock_manager:
    from graph import recaizade_node, RECAIZADE_SYSTEM_PROMPT

    # Setup Mock Model
    mock_model = MagicMock()
    mock_manager.get_model.return_value = mock_model
    mock_model.bind_tools.return_value = mock_model

    # Define validation logic
    def run_test():
        print("Starting ReAct Loop Verification...")
        
        # Scenario: Model calls tool, then returns text
        # Response 1: Tool Call
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "read_file",
                "args": {"filepath": "test.txt"},
                "id": "call_123"
            }]
        )
        
        # Response 2: Final Text
        final_text_msg = AIMessage(content="The file contains: File content")
        
        # Configure mock side effects
        mock_model.invoke.side_effect = [tool_call_msg, final_text_msg]
        
        # Initial State
        state = {"messages": [HumanMessage(content="Read test.txt")]}
        
        # Run Node
        result = recaizade_node(state)
        messages = result['messages']
        
        print(f"Total new messages: {len(messages)}")
        
        # Verify Sequence
        # 0: Tool Call (AIMessage)
        # 1: Tool Output (ToolMessage)
        # 2: Final Response (AIMessage)
        
        if len(messages) != 3:
            print(f"FAILURE: Expected 3 messages, got {len(messages)}")
            for m in messages: print(m)
            return
            
        if not messages[0].tool_calls:
            print("FAILURE: First message is not a tool call")
            return
            
        if not isinstance(messages[1], ToolMessage):
            print("FAILURE: Second message is not a ToolMessage")
            return
            
        if messages[2].content != "The file contains: File content":
            print(f"FAILURE: Final message content mismatch: {messages[2].content}")
            return
            
        print("SUCCESS: ReAct loop correctly handled tool call and final response.")

    if __name__ == "__main__":
        run_test()
