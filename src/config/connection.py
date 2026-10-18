import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
missing = [name for name in ("BASE_URL", "API_KEY") if not os.getenv(name)]
if missing:
    raise SystemExit(
        f"NanoHarness needs {', '.join(missing)}. See README.md for setup."
    )
client = OpenAI(base_url=os.environ["BASE_URL"], api_key=os.environ["API_KEY"])

def get_model_name() -> str:
    models = client.models.list().data
    if not models:
        raise RuntimeError("No model is loaded in the API server.")
    else:
        return models[0].id