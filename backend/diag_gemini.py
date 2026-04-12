import sys, os
sys.path.append(os.getcwd())
from ml.gemini_service import get_model

try:
    model = get_model()
    resp = model.generate_content("Testing connection. Reply with 'OK' if you can read this.")
    print(f"DIAGNOSTIC: Gemini Connection {resp.text.strip()}")
except Exception as e:
    print(f"DIAGNOSTIC: Gemini Connection FAILED: {e}")
