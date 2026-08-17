import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

qroq_models=["openai/gpt-oss-120b","openai/gpt-oss-20b"]

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

models = client.models.list()

for model in models.data:
    print(model)