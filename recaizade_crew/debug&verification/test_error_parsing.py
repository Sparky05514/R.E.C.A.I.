import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Mock the dependencies
import sys
import os

# Create a mock for model_manager
mock_model_manager = MagicMock()
mock_model_manager.provider = "gemini"

# Mock config
mock_config = MagicMock()
mock_config.get.return_value = []

# Mock tools
mock_tool_funcs = MagicMock()
mock_tool_funcs.read_file.return_value = "Error: File not found"

with patch.dict('sys.modules', {
    'agents': MagicMock(model_manager=mock_model_manager),
    'config_manager': MagicMock(config=mock_config),
    'tools': mock_tool_funcs
}):
    # Now import after patching
    from graph import invoke_model_with_fallback, recaizade_node

async def test_error_parsing():
    print("--- Testing Error Parsing ---")
    
    test_cases = [
        ("Resource has been exhausted (e.g. check quota).", "Rate limit exceeded or Quota exhausted"),
        ("429 Too Many Requests", "Rate limit exceeded or Quota exhausted"),
        ("Invalid API key", "Invalid or expired API Key"),
        ("The service is currently unavailable.", "Service unavailable"),
        ("Deadline exceeded", "Connection timeout"),
        ("Some other weird error", "Unknown API Error")
    ]
    
    for error_str, expected_reason in test_cases:
        mock_model_manager.provider = "gemini"
        mock_model = MagicMock()
        mock_model.ainvoke.side_effect = Exception(error_str)
        mock_model_manager.get_model.return_value = mock_model
        
        # Mock switch_to_ollama to change provider
        def switch():
            mock_model_manager.provider = "ollama"
        mock_model_manager.switch_to_ollama.side_effect = switch
        
        # Second call for Ollama
        mock_ollama_model = MagicMock()
        mock_ollama_model.ainvoke = AsyncMock(return_value=AIMessage(content="Ollama response"))
        
        # We need get_model to return the mock_ollama_model on second call
        def get_model(role):
            if mock_model_manager.provider == "ollama":
                return mock_ollama_model
            return mock_model
        
        mock_model_manager.get_model.side_effect = get_model
        
        response, alert = await invoke_model_with_fallback("recaizade", [HumanMessage(content="test")])
        
        print(f"DEBUG: response={response}")
        print(f"DEBUG: alert={alert}")
        
        assert alert is not None
        assert expected_reason in alert
        assert "Ollama response" in str(response.content)
        print(f"PASS: '{error_str}' -> '{expected_reason}'")

async def test_recaizade_node_alert_visibility():
    print("\n--- Testing Alert Visibility in recaizade_node ---")
    
    mock_model_manager.provider = "gemini"
    mock_model = MagicMock()
    mock_model.ainvoke.side_effect = Exception("429 Rate Limit")
    mock_model_manager.get_model.return_value = mock_model
    
    def switch():
        mock_model_manager.provider = "ollama"
    mock_model_manager.switch_to_ollama.side_effect = switch
    
    mock_ollama_model = MagicMock()
    mock_ollama_model.ainvoke = AsyncMock(return_value=AIMessage(content="Ollama response"))
    
    def get_model(role):
        if mock_model_manager.provider == "ollama":
            return mock_ollama_model
        return mock_model
    mock_model_manager.get_model.side_effect = get_model
    
    state = {"messages": []}
    result = await recaizade_node(state)
    
    messages = result["messages"]
    assert len(messages) == 2
    assert "[SYSTEM ALERT]" in messages[0].content
    assert "Rate limit" in messages[0].content
    assert "Ollama response" in messages[1].content
    print("PASS: Alert is prepended to result messages.")

if __name__ == "__main__":
    asyncio.run(test_error_parsing())
    asyncio.run(test_recaizade_node_alert_visibility())
