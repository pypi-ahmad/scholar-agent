import os
from langchain_google_genai import ChatGoogleGenerativeAI

# L-03: Corrected model name to a current GA identifier.
# C-04: Removed @retry from the constructor — ChatGoogleGenerativeAI() does no
#        network I/O; retries must wrap the .invoke() call, which LangChain
#        handles internally via max_retries=3 on the model object.
# S-03: Removed load_dotenv() — utility modules must not call load_dotenv();
#        only entry points (main.py, streamlit_app.py) should own env loading.
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"


def get_llm(model_name: str = GEMINI_DEFAULT_MODEL, temperature: float = 0.2):
    """
    Returns an instance of ChatGoogleGenerativeAI.
    Transient API failures are handled by LangChain's built-in max_retries.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set.")

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        max_retries=3,
    )


def get_json_llm(model_name: str = GEMINI_DEFAULT_MODEL, temperature: float = 0.2):
    """
    Returns an instance configured specifically for structured/JSON outputs.
    """
    return get_llm(model_name=model_name, temperature=temperature)
