import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    for m in genai.list_models():
        print(f"Model: {m.name} | Methods: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error: {e}")
