import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "")
print(f"Loaded GEMINI_API_KEY starting with: {api_key[:10]}... (total length: {len(api_key)})")

if not api_key:
    print("Error: GEMINI_API_KEY not found in env")
    exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("GenAI Client initialized. Making standard list_models call to verify API key...")
    models = client.models.list()
    print("Success! Your API key is valid. Available models:")
    for m in list(models)[:5]:
        print(f" - {m.name}")
except Exception as e:
    print(f"\nAPI Verification Failed!")
    print(f"Error: {e}")
