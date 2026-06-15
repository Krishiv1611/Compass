import os
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
def llm():
    load_dotenv()
    model=ChatOpenRouter(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model="google/gemma-4-31b-it:free"
    )
    return model