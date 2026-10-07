from openai import OpenAI
import os

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY) #establises the connection

models_response = client.models.list() #gets the available models

model_name = models_response.data[0].id

print(model_name[0])
response = client.responses.create(
    model="gpt-5.5",
    instructions="You are a coding assistant that talks like a pirate.",
    input="How do I check if a Python object is an instance of a class?",
)

print(response.output_text)