import os
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from graph import app_graph

load_dotenv()

async def test_chat():
    print("--- Testing Recaizade Chat ---")
    inputs = {"messages": [HumanMessage(content="Hello, who are you?")]}
    async for output in app_graph.astream(inputs):
        for key, value in output.items():
            print(f"Node '{key}':")
            # print(value)
            if "messages" in value:
                print(f"Response: {value['messages'][0].content}")

async def test_task():
    print("\n--- Testing Task Delegation ---")
    # This might fail if API key is invalid or specific capabilities are missing with Free tier, but let's try.
    inputs = {"messages": [HumanMessage(content="/task Create a file named 'test_file.txt' with content 'Hello Crew'")]}
    
    # We set a limit to avoid infinite loops if any
    step_count = 0
    async for output in app_graph.astream(inputs):
        step_count += 1
        for key, value in output.items():
            print(f"Node '{key}' executed.")
            if "messages" in value:
                last_msg = value['messages'][-1]
                print(f"Last Msg from {key}: {last_msg.content[:100]}...")
        
        if step_count > 10:
            break

async def test_recaizade_tools():
    print("\n--- Testing Recaizade Tool Usage ---")
    inputs = {"messages": [HumanMessage(content="Please list the current directory for me.")]}
    async for output in app_graph.astream(inputs):
        for key, value in output.items():
            print(f"Node '{key}':")
            if "messages" in value:
                print(f"Response: {value['messages'][0].content}")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY not found in env. Tests might fail.")
    
    # Run async tests
    asyncio.run(test_chat())
    # asyncio.run(test_task()) # verifying task might write files, be careful.
    asyncio.run(test_recaizade_tools())
