import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

models_to_test = [
    'models/gemini-2.0-flash',
    'models/gemini-1.5-flash',
    'models/gemini-1.5-pro',
    'models/gemini-1.0-pro',
    'models/gemini-1.5-flash-8b',
    'gemini-1.5-flash',
    'gemini-2.0-flash'
]

results = []
for m_name in models_to_test:
    try:
        model = genai.GenerativeModel(m_name)
        resp = model.generate_content("Hi")
        print(f"SUCCESS: {m_name}")
        results.append(m_name)
        break # Found one!
    except Exception as e:
        print(f"FAIL: {m_name} | {e}")

if results:
    print(f"RECOMMENDED_MODEL: {results[0]}")
else:
    print("ALL_MODELS_FAILED")
