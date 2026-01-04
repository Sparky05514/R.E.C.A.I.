from config_manager import config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

def get_recaizade_prompt():
    stored = config.get("prompts", "recaizade")
    if stored: return stored
    tools = config.get("behavior", "recaizade_tools")
    tools_str = ", ".join([f"'{t}'" for t in tools])
    return f"""You are Recaizade, a helpful and intelligent AI assistant.
Your goal is to assist the user. You are the specific interface to a 'Crew' of other AI agents.

You have access to these tools: {tools_str}.
You can use these tools to directly help the user or explore the project.

If the user wants to perform a complex, multi-step coding task, you should suggest they use the /task command or recognize if they used it.
While you have tools, the Crew is specialized for intensive coding and implementation tasks.

IMPORTANT: You must follow this cognitive flow for EVERY interaction that might involve tools:
1. THINKING: Analyze the request and plan your actions within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you decide to use a tool, explicitly state: "I will now make a tool call to [tool_name] to [purpose]."
3. ACTION: Make the tool call.
4. FOLLOW-UP: After the tool executes, provide a conversational response explaining the result (handled by the system loop).

Maintain a friendly and professional persona.
"""

def get_coder_prompt():
    stored = config.get("prompts", "coder")
    if stored: return stored
    return """You are the Coder for the crew.
Your task is to write clean, efficient, and well-documented code based on the human request and Recaizade's coordination.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the task and plan your code architecture within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you decide to use a tool, explicitly state: "I will now make a tool call to [tool_name] to [purpose]."
3. ACTION: Make the tool call or provide the code block.
4. FOLLOW-UP: After the action, provide a brief summary of what you implemented.

When providing code, use markdown blocks with filenames clearly indicated before the block (e.g., 'File: main.py').
"""

def get_executor_prompt():
    stored = config.get("prompts", "executor")
    if stored: return stored
    tools = config.get("behavior", "crew_tools")
    tools_str = ", ".join([f"'{t}'" for t in tools])
    return f"""You are the Executor. You don't write code; you take code provided by the Coder and ensure it is saved correctly using file tools.
You have access to these tools: {tools_str}.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the Coder's output and identify which files need to be written/modified within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: Explicitly state: "I will now make a tool call to 'write_file' to save [filename]."
3. ACTION: Execute the tool calls.
4. FOLLOW-UP: Confirm that the files have been processed.
"""

def get_reviewer_prompt():
    stored = config.get("prompts", "reviewer")
    if stored: return stored
    return """You are the Reviewer. Your role is to examine the code written and saved by the Coder and Executor.
Check for bugs, security issues, performance bottlenecks, and adherence to requirements.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Analyze the implementation against the requirements within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: If you need to read a file to review it, state: "I will now make a tool call to 'read_file' to examine [filename]."
3. ACTION: Read the file or provide your feedback.
4. FOLLOW-UP: Provide a structured review. 

If everything is correct, Respond with 'REVIEW_PASSED'. If there are issues, suggest changes and respond with 'REVIEW_FAILED'.
"""

def get_documenter_prompt():
    stored = config.get("prompts", "documenter")
    if stored: return stored
    return """You are the Documenter. Your job is to create reports and maintain project memory.

IMPORTANT: You must follow this cognitive flow:
1. THINKING: Plan the report and memory updates based on the crew's actions within <thinking>...</thinking> tags.
2. ANNOUNCEMENT: State: "I will now make a tool call to 'write_file' to update project documentation."
3. ACTION: Make the tool call or output the report.
4. FOLLOW-UP: Confirm completion.

You have two main responsibilities:
1. User Reporting: Write a clear progress report for the user. Summarize what was done and current status.
2. Bot Memory: Write a detailed technical log for the crew to read in future steps. Include technical decisions, file paths, etc.
"""

class ModelManager:
    def __init__(self):
        self.provider = config.get("provider")
        self.models = {}
        self.reload_models()
        
    def reload_models(self):
        self.provider = config.get("provider")
        if self.provider == "gemini":
            self._initialize_gemini()
        else:
            self._initialize_ollama()

    def _initialize_gemini(self):
        api_key = config.get("google_api_key")
        model_name = config.get("models", "gemini")
        temp = config.get("behavior", "temperature")
        crew_temp = config.get("behavior", "crew_temperature")
        
        try:
            self.models['recaizade'] = ChatGoogleGenerativeAI(
                model=model_name, google_api_key=api_key, temperature=temp
            )
            self.models['crew'] = ChatGoogleGenerativeAI(
                model=model_name, google_api_key=api_key, temperature=crew_temp
            )
            print(f"ModelManager: Initialized Gemini models ({model_name}).")
        except Exception as e:
            print(f"ModelManager: Failed to initialize Gemini: {e}")
            self.provider = "ollama"
            self._initialize_ollama()

    def _initialize_ollama(self):
        chat_model = config.get("models", "ollama_chat")
        coder_model = config.get("models", "ollama_coder")
        temp = config.get("behavior", "temperature")
        crew_temp = config.get("behavior", "crew_temperature")
        base_url = config.get("ollama_base_url")

        # Recaizade / General
        self.models['recaizade'] = ChatOllama(model=chat_model, temperature=temp, base_url=base_url)
        # We split crew models for Ollama
        self.models['crew_chat'] = ChatOllama(model=chat_model, temperature=crew_temp, base_url=base_url)
        self.models['crew_coder'] = ChatOllama(model=coder_model, temperature=crew_temp, base_url=base_url)
        print(f"ModelManager: Initialized Ollama models ({chat_model}, {coder_model}).")

    def get_model(self, role="recaizade"):
        """Get the appropriate model instance based on role and current provider."""
        if self.provider == "gemini":
            if role == "recaizade":
                return self.models['recaizade']
            else:
                return self.models['crew']
        else: # Ollama
            if role == "recaizade":
                return self.models['recaizade']
            elif role == "coder":
                return self.models['crew_coder']
            else: # executor, reviewer, documenter
                return self.models['crew_chat']

# Initialize Manager
model_manager = ModelManager()

# Update system prompt variables to be dynamic
RECAIZADE_SYSTEM_PROMPT = get_recaizade_prompt()
CODER_SYSTEM_PROMPT = get_coder_prompt()
EXECUTOR_SYSTEM_PROMPT = get_executor_prompt()
REVIEWER_SYSTEM_PROMPT = get_reviewer_prompt()
DOCUMENTER_SYSTEM_PROMPT = get_documenter_prompt()

def refresh_prompts():
    global RECAIZADE_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, EXECUTOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT, DOCUMENTER_SYSTEM_PROMPT
    RECAIZADE_SYSTEM_PROMPT = get_recaizade_prompt()
    CODER_SYSTEM_PROMPT = get_coder_prompt()
    EXECUTOR_SYSTEM_PROMPT = get_executor_prompt()
    REVIEWER_SYSTEM_PROMPT = get_reviewer_prompt()
    DOCUMENTER_SYSTEM_PROMPT = get_documenter_prompt()
