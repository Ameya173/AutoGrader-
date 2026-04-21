import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=key)

model_name = 'models/gemini-2.0-flash'
print(f"Testing model: {model_name}")
try:
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Hello, are you working? Respond with 'YES'.")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
