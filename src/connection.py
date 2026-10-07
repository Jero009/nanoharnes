import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(base_url=os.environ["BASE_URL"],api_key=os.environ["API_KEY"]) # establish a connection to the API server

def get_model_name() -> str:
    models = client.models.list().data
    if not models:
        raise RuntimeError("No model is loaded in the API server.")
    else:
        return models[0].id