"""
Gemini API Service — Ultra-Fast & Stable Version
- Direct target: Gemini 2.5 Flash
- Removed slow fallback loops to prevent browser "Failed to fetch" timeouts
- Optimized for speed and reliability under 5 RPM limit
"""
import os, base64, json, re, traceback, time
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv

load_dotenv()
_model = None

# Safety Settings
SAFETY_NONE = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

def _clean_qnum(q):
    """Normalize question numbers."""
    if not q: return "?"
    return str(q).strip().lstrip('Qq').strip('. ')

def get_model():
    global _model
    if _model is not None:
        return _model
    
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    
    genai.configure(api_key=key)
    
    # Direct use of the user's identified working model
    preferred = 'models/gemini-2.5-flash'
    print(f"DEBUG: Connecting to {preferred}...")
    _model = genai.GenerativeModel(preferred)
    return _model

def _safe_json(text, fallback):
    if not text: return fallback
    clean = re.sub(r'```json\s*', '', text)
    clean = re.sub(r'```\s*', '', clean).strip()
    try:
        data = json.loads(clean)
        return data if isinstance(data, (list, dict)) else fallback
    except:
        m = re.search(r'[\[{][\s\S]*[\]}]', clean)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return fallback

def _img_part(path):
    with open(path,'rb') as f: data = f.read()
    ext = path.split('.')[-1].lower()
    mime = 'application/pdf' if ext=='pdf' else f'image/{ext}'
    return {'mime_type': mime, 'data': data}

def extract_questions_from_paper(file_path):
    """
    Standard OCR extraction for Reference Paper.
    UPGRADED: Precision mode for 100% mark/question coverage.
    """
    try:
        model = get_model()
        prompt = """
        ACT AS AN ELITE EXAM ANALYST & OCR SPECIALIST.
        You are scanning a REFERENCE ANSWER PAPER. You must capture EVERY mark and question.
        
        STEP 1: AUDIT THE PAPER
        - Find "Total Marks", "Maximum Marks", or "M.M." (e.g., 20, 50, 100).
        - Count every distinct question block. 
        - Look at the right-hand margin; marks are often listed there in [brackets] or (parentheses).
        - WARNING: Do not confuse question numbers like "1)" or "i)" with marks. A question labeled "1)" might be worth 7 marks.
        
        STEP 2: SCAN FOR HIDDEN QUESTIONS
        - Ensure you don't miss small questions at the end of pages or at the very top.
        - Check if questions have sub-parts (like 1a, 1b).
        
        STEP 3: VERIFY THE MATH
        - Sum all the marks you found. If the sum doesn't match the "Total Marks" on the paper, RE-SCAN the document carefully to find missing marks.
        
        OUTPUT FORMAT (JSON ONLY):
        [
          {
            "number": "string (CAPTURE SUB-QUESTIONS e.g., 1a, 1b, 1c)",
            "text": "full question wording",
            "marks": number (BE PRECISE - e.g., 6, 7, 7),
            "answerText": "the model/reference answer text",
            "keywords": ["essential", "terms"],
            "hasDiagram": true/false (Set true if the question asks for or includes a diagram/sketch/graph/figure)
          }
        ]
        """
        
        part = _img_part(file_path)
        resp = model.generate_content([part, prompt], safety_settings=SAFETY_NONE)
        
        if not resp.text: raise ValueError("AI Empty Response")
        
        data = _safe_json(resp.text, [])
        for item in data:
            item['number'] = _clean_qnum(item.get('number'))
            # Robust mark conversion
            try: item['marks'] = float(item.get('marks', 5))
            except: item['marks'] = 5.0
            
        return data
        
    except exceptions.ResourceExhausted:
        print("WARNING: Quota hit. Use short delay.")
        # Minimal wait to not trigger browser timeout
        time.sleep(2) 
        # Final try
        try:
            resp = model.generate_content([_img_part(file_path), prompt], safety_settings=SAFETY_NONE)
            data = _safe_json(resp.text, [])
            for item in data: item['number'] = _clean_qnum(item.get('number'))
            return data
        except: return []
    except Exception as e:
        print(f"ERROR Extraction: {e}")
        return []

def extract_answer_sheet(file_path, questions):
    """
    OCR for student answers. 
    UPGRADED: Context-Aware Transcription for messy handwriting.
    """
    try:
        model = get_model()
        q_ctx = "\n".join([f"{_clean_qnum(q.get('number'))}: {q.get('text')[:100]}" for q in questions])
        prompt = f"""
        ACT AS AN EXPERT HANDWRITING DECODER.
        Transcribe the handwritten student answers from this image.
        
        CRITICAL RULES:
        1. CONTEXTUAL RECOVERY: Student handwriting may be messy. Use the context of the question (provided below) to infer the most likely words.
        2. IGNORE STRUCK-THROUGH TEXT: If a student has drawn a line through a sentence or a block of text, DO NOT transcribe it. Treat it as deleted.
        3. DO NOT SKIP: Even if a sentence is messy, transcribe your best guess (unless it is struck through).
        4. NO SUMMARIES: Write the exact text as seen or intended.
        5. DIAGRAMS: Note if a diagram/image is present for that question.
        
        QUESTION CONTEXT:
        {q_ctx}
        
        OUTPUT FORMAT (JSON ONLY):
        [
          {{
            "questionNumber": "match the IDs from context above",
            "answerText": "transcribed text",
            "hasDiagram": true/false (Set true if the student has drawn a diagram, sketch, or box for this question)
          }}
        ]
        """
        
        resp = model.generate_content([_img_part(file_path), prompt], safety_settings=SAFETY_NONE)
        
        if not resp.text: raise ValueError("AI Empty Response")
        data = _safe_json(resp.text, [])
        for item in data:
            item['questionNumber'] = _clean_qnum(item.get('questionNumber'))
        return data
        
    except exceptions.ResourceExhausted:
        print("WARNING: Student OCR Quota hit. Using 5-second backoff...")
        time.sleep(5)
        try:
            resp = model.generate_content([_img_part(file_path), prompt], safety_settings=SAFETY_NONE)
            data = _safe_json(resp.text, [])
            for item in data: item['questionNumber'] = _clean_qnum(item.get('questionNumber'))
            return data
        except Exception as retry_e:
            raise RuntimeError("Gemini Quota Exceeded (5 RPM). Please wait 30 seconds and try again.")
            
    except Exception as e:
        print(f"ERROR Student OCR: {e}")
        # Allow it to crash upward so the UI knows the OCR failed, instead of grading an empty page
        raise RuntimeError(f"OCR Extraction Failed: {str(e)}")

def grade_answer_feedback(question_text, model_answer, student_answer, marks, ml_score):
    """
    Teacher Persona Grading: Upgraded Prompt for Highest Accuracy.
    - Focuses on "Concept over Syntax"
    - Identifies specific "Mistakes" and "Improvement Paths"
    """
    try:
        model = get_model()
        prompt = f"""
        PERSONA: You are a kind, sentimental, and supportive university teacher. 
        Your goal is to ENCOURAGE students by finding reasons to give them marks, not reasons to subtract them.
        
        - TARGET ACCURACY: Aim to match a "Strict Teacher's Sentiment"—looking for depth and effort.

        GRADING PHILOSOPHY:
        - DEPTH OVER BREVITY: For high-mark questions (5, 7, 10 marks), a single line or extremely short answer is NOT enough. Penalize heavily for lack of detail/completeness even if the core idea is there.
        - CONCEPT OVER SYNTAX: If the student understands the "spirit" of the answer, give credit, BUT only if they provide enough detail to justify the marks.
        - BE FAIR: If an answer is clearly incomplete for the marks assigned, give a low score (e.g. 0-2 out of 7).
        - IGNORE OCR ERRORS: Assume intended words if the context fits.

        QUESTION ({marks} marks total): {question_text}

        REFERENCE ANSWER (Ideal points):
        {model_answer}

        STUDENT'S ANSWER:
        {student_answer}

        MARKING INSTRUCTIONS:
        1. Identify the core concepts in the reference.
        2. Look for ANY hint of those concepts in the student's answer.
        3. Award marks based on understanding. Even if it is disorganized, if the logic is there, be generous.
        4. DEPTH CHECK: If the question is worth {marks} marks and the answer is only one sentence, it is "Critically Incomplete". Award very few marks.
        5. BENEFIT OF THE DOUBT: Only award the mark if the student has provided a reasonably comprehensive answer for the points required.
        6. suggestedScore = (calculated percentage 0-100) — Be a strict but fair and encouraging evaluator.

        OUTPUT JSON ONLY:
        {{
          "feedback": "2-3 sentences — a supportive and encouraging comment",
          "strengths": ["What they did well"],
          "mistakes": ["Gently point out what was missed, explaining why it's important"],
          "improvements": ["One clear tip for next time"],
          "suggestedScore": 0-100
        }}
        """
        
        resp = model.generate_content(prompt, safety_settings=SAFETY_NONE)
        res = _safe_json(resp.text, {})
        # Ensure raw score is capped and fallback to ML if AI fails (ml_score is already 0-100)
        res['suggestedScore'] = max(0, min(100, float(res.get('suggestedScore', ml_score))))
        return res
    except Exception as e:
        print(f"DEBUG: Grade Feedback Error: {e}")
        return {
            'feedback': 'Detailed AI analysis was unavailable for this answer.',
            'strengths': [],
            'mistakes': ['Analysis could not pinpoint mistakes due to server error.'],
            'improvements': ['Consider manual verification.'],
            'suggestedScore': ml_score if ml_score else 0
        }

def generate_student_report(student_name, exam_title, grades, percentage):
    try:
        model = get_model()
        prompt = f"Summary report for {student_name} on {exam_title} ({percentage}%). Be brief."
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except:
        return f"{student_name} scored {percentage}%."
