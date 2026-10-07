# loop.py
from connection import client, get_model_name

def loop():
    model_name = get_model_name()
    messages = [{"role": "system", "content": "You are are a helpful assistant."}]

    while True:
        user_input = input("\n User: ")
        messages.append({"role": "user", "content": user_input})

        response_stream = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        stream=True,
                        temperature=0.6,          # 0.6 - 0.7 prevents rigid deterministic loops
                        presence_penalty=0.3,     # Penalizes words the model has already used
                        frequency_penalty=0.3,    # Discourages repeating the exact same phrases
        )
        print("Nanocode: ",end="")
        response = ""
        for chunk in response_stream:
            token = chunk.choices[0].delta.content or ""
            print(token, end="", flush=True)
            response += token

        messages.append({"role": "assistant", "content": response})