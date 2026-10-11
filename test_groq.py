import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
print(f"API Key loaded: {groq_api_key[:8]}... (length: {len(groq_api_key) if groq_api_key else 0})")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=groq_api_key
)

try:
    print("\nFetching active Groq models...")
    models_response = client.models.list()
    active_models = [m.id for m in models_response.data]
    print("Available Models in your account:")
    for model_id in active_models:
        print(f" - {model_id}")

    # Pick the first available model to test
    if active_models:
        test_model = active_models[0]
        print(f"\nTesting simple call with model: '{test_model}'...")
        res = client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print("Success! Response from Groq:")
        print(res.choices[0].message.content)
    else:
        print("No models found in response.")

except Exception as e:
    print(f"\nError encountered: {e}")