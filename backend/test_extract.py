import sys
import os
from ml.gemini_service import extract_questions_from_paper

def test():
    # Use any image in the test data or just an empty one if not available
    # For now, let's just see if it runs
    try:
        print("Testing extraction...")
        # create a dummy image
        with open("dummy.png", "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        res = extract_questions_from_paper("dummy.png")
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
