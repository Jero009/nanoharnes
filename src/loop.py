# loop.py
from connection import client, get_model_name

def loop():
    model_name = get_model_name()
    messages = [{"role": "system", "content": "You are are a helpful assistant."}]

    while True:
        user_input = input("User: ")
        messages.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )

        answer = response.choices[0].message.content 

        print(f"\nNanocode: {answer}\n")
        messages.append({"role": "assistant", "content": answer})