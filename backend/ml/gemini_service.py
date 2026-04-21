"""
Gemini API Service — High-Performance Split Pipeline
- Target: Gemini 2.0 Flash (Optimized for speed)
- Split Pipeline: OCR Extraction + Creative Enrichment to prevent timeouts
- Safety: BLOCK_NONE for academic reliability
"""
import os, base64, json, re, traceback, time, uuid, io
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv
import pdfplumber
from pptx import Presentation

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
    
    # Automatic Model Selection to prevent 404 errors
    # We try 1.5-flash (high quota) first, then fallback to others
    models_to_try = [
        'gemini-1.5-flash',
        'gemini-flash-latest',
        'gemini-1.5-flash-001',
        'gemini-1.5-flash-002',
        'gemini-2.0-flash'  # Last resort due to low quota
    ]
    
    for model_name in models_to_try:
        try:
            print(f"DEBUG: Attempting to connect to {model_name}...")
            test_model = genai.GenerativeModel(model_name)
            # Minimal test call to verify name/quota (no images to save bandwidth)
            test_model.generate_content("ping") 
            _model = test_model
            print(f"DEBUG: Successfully connected to {model_name}!")
            return _model
        except exceptions.NotFound:
            print(f"DEBUG: Model {model_name} not found. Trying next...")
            continue
        except Exception as e:
            # If it's a quota issue, we might still want this model, 
            # but let's see if another one is available first.
            print(f"DEBUG: Error with {model_name}: {e}")
            last_error = e
            continue
    
    # Fallback to the first one if all failed
    print(f"WARNING: All model attempts failed. Defaulting to 1.5-flash. Error: {last_error}")
    _model = genai.GenerativeModel('gemini-1.5-flash')
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
    """Utility to prepare image/pdf for Gemini API."""
    with open(path,'rb') as f: data = f.read()
    ext = path.split('.')[-1].lower()
    mime = 'application/pdf' if ext=='pdf' else f'image/{ext}'
    return {'mime_type': mime, 'data': data}

def extract_text_from_pdf(path):
    """Extract text from PDF using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        print(f"ERROR PDF Extract: {e}")
    return text.strip()

def extract_text_from_pptx(path):
    """Extract text from PPTX slides."""
    text = ""
    try:
        prs = Presentation(path)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
    except Exception as e:
        print(f"ERROR PPTX Extract: {e}")
    return text.strip()

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

def extract_paper_structure(file_path):
    """
    STEP 1: OCR PURE EXTRACTION
    Extracts question numbers, text, and marks from a blank paper.
    """
    try:
        model = get_model()
        prompt = """
        ACT AS AN EXPERT OCR ANALYST.
        Scan this Question Paper and extract the structured list of questions.

        CRITICAL RULES:
        1. Capture EVERY question number and text.
        2. Look for marks/weightage (usually in brackets at the right margin).
        3. If no marks are found, default to 5.0.
        4. Capture sub-questions (e.g., 1a, 1b) precisely.

        OUTPUT JSON ONLY:
        [
          {
            "number": "string",
            "text": "full question",
            "marks": number
          }
        ]
        """
        part = _img_part(file_path)
        resp = model.generate_content([part, prompt], safety_settings=SAFETY_NONE)
        if not resp.text: raise ValueError("AI Empty Response")
        data = _safe_json(resp.text, [])
        for item in data:
            item['number'] = _clean_qnum(item.get('number'))
            try: item['marks'] = float(item.get('marks', 5.0))
            except: item['marks'] = 5.0
        return data
    except exceptions.ResourceExhausted:
        print("WARNING: Quota hit during OCR. Retrying in 10s...")
        time.sleep(10)
        try:
            resp = model.generate_content([_img_part(file_path), prompt], safety_settings=SAFETY_NONE)
            data = _safe_json(resp.text, [])
            for item in data: item['number'] = _clean_qnum(item.get('number'))
            return data
        except: return []
    except Exception as e:
        print(f"ERROR Structure Extraction: {str(e)}")
        traceback.print_exc()
        return []

def enrich_questions_with_answers(questions, subject_hint=""):
    """
    STEP 2: CONTENT GENERATION
    Generates model answers, rubrics, and sources for the extracted questions.
    """
    if not questions: return []
    try:
        model = get_model()
        q_json = json.dumps(questions)
        prompt = f"""
        ACT AS AN ELITE PROFESSOR.
        Subject: {subject_hint}

        For the following questions, generate:
        1. A perfect, concise MODEL ANSWER.
        2. 2-3 Assessment Parameters (rubrics) with weights that sum to the total marks.
        3. Relevant academic sources/concepts.

        QUESTIONS:
        {q_json}

        OUTPUT JSON ONLY (Maintain original order, add answerText, relevantSources, assessmentParameters):
        [
          {{
            "number": "...",
            "text": "...",
            "marks": ...,
            "answerText": "model answer",
            "relevantSources": ["Concept"],
            "assessmentParameters": [
              {{"parameter": "Defining concept", "weight": 2.0}}
            ],
            "hasDiagram": true/false
          }}
        ]
        """
        resp = model.generate_content(prompt, safety_settings=SAFETY_NONE)
        if not resp.text: raise ValueError("AI Empty Response")
        data = _safe_json(resp.text, [])
        return data if data else questions # Fallback to original if enrichment fails
    except exceptions.ResourceExhausted:
        print("WARNING: Quota hit during Enrichment. Retrying in 12s...")
        time.sleep(12)
        try:
            resp = model.generate_content(prompt, safety_settings=SAFETY_NONE)
            return _safe_json(resp.text, questions)
        except: return questions
    except Exception as e:
        print(f"ERROR Question Enrichment: {e}")
        return questions

def generate_reference_book_from_paper(file_path):
    """
    LEGACY WRAPPER: Now uses the split pipeline internally.
    """
    print("DEBUG: Using legacy wrapper for Answer Book generation...")
    structure = extract_paper_structure(file_path)
    if not structure: return []
    return enrich_questions_with_answers(structure)

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
        print("WARNING: Student OCR Quota hit. Sleeping 5s to recover...")
        time.sleep(5)
        try:
            resp = model.generate_content([_img_part(file_path), prompt], safety_settings=SAFETY_NONE)
            data = _safe_json(resp.text, [])
            for item in data: item['questionNumber'] = _clean_qnum(item.get('questionNumber'))
            return data
        except Exception as retry_e:
            raise RuntimeError("Gemini API is busy. Please wait 60 seconds and try again.")
            
    except Exception as e:
        print(f"ERROR Student OCR: {e}")
        # Allow it to crash upward so the UI knows the OCR failed, instead of grading an empty page
        raise RuntimeError(f"OCR Extraction Failed: {str(e)}")

def grade_answer_feedback(question_text, model_answer, student_answer, marks, ml_score, study_material=None):
    """
    Teacher Persona Grading: Upgraded Prompt for Highest Accuracy.
    - Focuses on "Concept over Syntax"
    - Identifies specific "Mistakes" and "Improvement Paths"
    - Uses Study Material context if provided
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

        RUBRIC / ASSESSMENT PARAMETERS:
        {model_answer.get('assessmentParameters', []) if isinstance(model_answer, dict) else 'N/A'}

        RELEVANT SOURCES/CONCEPTS:
        {model_answer.get('relevantSources', []) if isinstance(model_answer, dict) else 'N/A'}

        ADDITIONAL REFERENCE MATERIAL (Context from Teacher PDFs/PPTs):
        {study_material if study_material else 'No additional material provided.'}

        QUESTION ({marks} marks total): {question_text}

        REFERENCE ANSWER (Ideal points):
        {model_answer.get('answerText', model_answer) if isinstance(model_answer, dict) else model_answer}

        STUDENT'S ANSWER:
        {student_answer}

        MARKING INSTRUCTIONS:
        1. Identify the core concepts in the reference.
        2. Evaluate the student's answer against the specific ASSESSMENT PARAMETERS provided above.
        3. Award marks for each parameter found.
        4. DEPTH CHECK: If the question is worth {marks} marks and the answer is only one sentence, it is "Critically Incomplete". Award very few marks.
        5. suggestedScore = (calculated percentage 0-100) — Be a strict but fair and encouraging evaluator.

        OUTPUT JSON ONLY:
        {{
          "feedback": "2-3 sentences — a supportive and encouraging comment",
          "strengths": ["What they did well"],
          "mistakes": ["Gently point out what was missed, explaining why it's important"],
          "improvements": ["One clear tip for next time"],
          "suggestedScore": 0-100
        }}
        """
        
        # Handle Quota Exceeded for individual calls
        try:
            resp = model.generate_content(prompt, safety_settings=SAFETY_NONE)
        except exceptions.ResourceExhausted:
            print("WARNING: Grading quota hit. Waiting 12 seconds...")
            time.sleep(12)
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

def grade_batch_feedback(student_name, exam_title, questions_batch, study_material=None):
    """
    Grades multiple questions AND generates a summary report narrative in a single call.
    questions_batch: list of {id, text, marks, modelAnswer, studentAnswer, mlScore}
    """
    try:
        model = get_model()
        
        # Prepare structured context for the AI
        q_entries = []
        for q in questions_batch:
            q_entries.append(f"""
--- QUESTION {q.get('number', '?')} ({q.get('marks', 5)} marks) ---
TEXT: {q.get('text')}
REFERENCE: {q.get('modelAnswer')}
STUDENT ANSWER: {q.get('studentAnswer')}
ML PRELIMINARY SCORE: {q.get('mlScore', 0)}%
""")

        context_block = "\n".join(q_entries)
        
        prompt = f"""
ACT AS AN ELITE UNIVERSITY PROFESSOR & FAIR GRADER.
Student: {student_name}
Exam: {exam_title}

Grade the student answers for the following questions based on the REFERENCE provided and the ADDITIONAL STUDY MATERIAL context.

GRADING PHILOSOPHY:
- BE FAIR & ENCOURAGING: Award marks for conceptual understanding.
- DEPTH CHECK: High-mark questions require detailed answers. Penalize for brevity.
- CONSISTENCY: Maintain a consistent standard across all questions.

ADDITIONAL STUDY MATERIAL CONTEXT:
{study_material if study_material else 'No additional material provided.'}

QUESTIONS TO GRADE:
{context_block}

OUTPUT FORMAT (JSON ONLY):
{{
  "grades": [
    {{
      "number": "string",
      "feedback": "2-3 sentences of supportive but honest feedback",
      "strengths": ["list"],
      "mistakes": ["list"],
      "improvements": ["list"],
      "suggestedScore": 0-100
    }}
  ],
  "overallNarrative": "A 2-3 sentence summary report addressed to the student about their overall performance."
}}
"""
        
        resp = model.generate_content(prompt, safety_settings=SAFETY_NONE)
        if not resp.text: raise ValueError("AI Empty Response")
        
        results = _safe_json(resp.text, {})
        return results
        
    except Exception as e:
        print(f"ERROR Batch Grading: {e}")
        return {"grades": [], "overallNarrative": ""}

def generate_student_report(student_name, exam_title, grades, percentage):
    try:
        model = get_model()
        prompt = f"Summary report for {student_name} on {exam_title} ({percentage}%). Be brief."
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except:
        return f"{student_name} scored {percentage}%."
