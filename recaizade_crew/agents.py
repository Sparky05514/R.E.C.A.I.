import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    # Fallback or error - relying on user to set it
    pass

# Models
from langchain_ollama import ChatOllama

# Model Configuration
GEMINI_MODEL = "gemini-3-flash-preview"
OLLAMA_CHAT_MODEL = "llama3.2"    # For Recaizade, Reviewer, Executor
OLLAMA_CODER_MODEL = "qwen2.5-coder" # For Coder

class ModelManager:
    def __init__(self, api_key):
        self.api_key = api_key
        self.provider = "gemini" # Default to Gemini
        self.models = {}
        self._initialize_gemini()
        
    def _initialize_gemini(self):
        try:
            self.models['recaizade'] = ChatGoogleGenerativeAI(
                model=GEMINI_MODEL, google_api_key=self.api_key, temperature=0.7
            )
            # Default crew model (Gemini)
            self.models['crew'] = ChatGoogleGenerativeAI(
                model=GEMINI_MODEL, google_api_key=self.api_key, temperature=0.2
            )
            print("ModelManager: Initialized Gemini models.")
        except Exception as e:
            print(f"ModelManager: Failed to initialize Gemini: {e}")
            self.switch_to_ollama()

    def _initialize_ollama(self):
        # Recaizade / General
        self.models['recaizade'] = ChatOllama(model=OLLAMA_CHAT_MODEL, temperature=0.7)
        # We split crew models for Ollama
        self.models['crew_chat'] = ChatOllama(model=OLLAMA_CHAT_MODEL, temperature=0.2)
        self.models['crew_coder'] = ChatOllama(model=OLLAMA_CODER_MODEL, temperature=0.2)
        print("ModelManager: Initialized Ollama models.")

    def switch_to_ollama(self):
        if self.provider == "ollama":
            return # Already switched
            
        print("ModelManager: Switching to Ollama...")
        self.provider = "ollama"
        self._initialize_ollama()
        
    def get_model(self, role="recaizade"):
        """Get the appropriate model instance based on role and current provider."""
        if self.provider == "gemini":
            if role == "recaizade":
                return self.models['recaizade']
            else:
                return self.models['crew'] # Gemini uses same model for crew
        else: # Ollama
            if role == "recaizade":
                return self.models['recaizade']
            elif role == "coder":
                return self.models['crew_coder']
            else: # executor, reviewer, documenter
                return self.models['crew_chat']

# Initialize Manager
model_manager = ModelManager(api_key)

# Deprecated: usage should be replaced by model_manager.get_model()
# Keeping for compatibility during migration if needed, but best to replace usage.
# recaizade_model = model_manager.get_model("recaizade")
# crew_model = model_manager.get_model("crew")

# Prompts
RECAIZADE_SYSTEM_PROMPT = """You are Recaizade, a helpful and intelligent AI assistant powered by Gemini 3 Flash.
Your goal is to assist the user. You are the specific interface to a 'Crew' of other AI agents.

You have access to tools to interact with the file system: 'read_file', 'write_file', 'list_directory', and 'delete_file'.
You can use these tools to directly help the user or explore the project.

If the user wants to perform a complex, multi-step coding task, you should suggest they use the /task command or recognize if they used it.
While you have tools, the Crew is specialized for intensive coding and implementation tasks.

IMPORTANT: You must follow this cognitive flow for EVERY interaction that might involve tools:
1. THINKING: Analyze the request and plan your actions within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you decide to use a tool, explicitly state: "I will now make a tool call to [tool_name] to [purpose]."
3. ACTION: Make the tool call.
4. FOLLOW-UP: After the tool executes, provide a conversational response explaining the result (handled by the system loop).

Example:
<thinking>User wants to list files. I should use 'list_directory'.</thinking>
I will now make a tool call to 'list_directory' to see the current files.
[Tool Call]

Maintain a friendly and professional persona.
"""

CODER_SYSTEM_PROMPT = """You are the Coder for the crew.
Your task is to write clean, efficient, and well-documented Python code based on the human request and Recaizade's coordination.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the task and plan your code architecture within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you decide to use a tool, explicitly state: "I will now make a tool call to [tool_name] to [purpose]."
3. ACTION: Make the tool call or provide the code block.
4. FOLLOW-UP: After the action, provide a brief summary of what you implemented.

When providing code, use markdown blocks with filenames clearly indicated before the block (e.g., 'File: main.py').
Example:
<thinking>I need to implement a calculator class.</thinking>
I will now make a tool call to 'write_file' to create calculator.py.
```python
class Calculator: ...
```
"""

EXECUTOR_SYSTEM_PROMPT = """You are the Executor. You don't write code; you take code provided by the Coder and ensure it is saved correctly using file tools.
You have access to 'write_file', 'read_file', 'list_directory', and 'delete_file'.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the Coder's output and identify which files need to be written/modified within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: Explicitly state: "I will now make a tool call to 'write_file' to save [filename]."
3. ACTION: Execute the tool calls.
4. FOLLOW-UP: Confirm that the files have been processed.
"""

REVIEWER_SYSTEM_PROMPT = """You are the Reviewer. Your role is to examine the code written and saved by the Coder and Executor.
Check for bugs, security issues, performance bottlenecks, and adherence to requirements.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the implementation against the requirements within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you need to read a file to review it, state: "I will now make a tool call to 'read_file' to examine [filename]."
3. ACTION: Read the file or provide your feedback.
4. FOLLOW-UP: Provide a structured review. 

If everything is correct, Respond with 'REVIEW_PASSED'. If there are issues, suggest changes and respond with 'REVIEW_FAILED'.
"""

DOCUMENTER_SYSTEM_PROMPT = """You are the Documenter. Your job is to create reports and maintain project memory.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Plan the report and memory updates based on the crew's actions within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: State: "I will now make a tool call to 'write_file' to update project documentation."
3. ACTION: Make the tool call or output the report.
4. FOLLOW-UP: Confirm completion.

You have two main responsibilities:
1. User Reporting: Write a clear progress report for the user. Summarize what was done and current status.
2. Bot Memory: Write a detailed technical log for the crew to read in future steps. Include technical decisions, file paths, etc.
"""
