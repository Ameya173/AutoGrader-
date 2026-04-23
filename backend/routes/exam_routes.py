"""Exam Routes"""
import os, uuid
from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename
from utils.local_db import create_exam, get_exam, update_exam, delete_exam, get_teacher_exams, get_published_exams, get_exam_submissions
from utils.auth import require_auth, require_teacher

exam_bp = Blueprint('exams', __name__)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__),'..','uploads','reference')
ALLOWED = {'pdf','png','jpg','jpeg','webp'}

def allowed(fn): return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

@exam_bp.route('/', methods=['GET'])
@require_auth
def list_exams():
    if g.role == 'teacher':
        return jsonify(get_teacher_exams(g.uid))
    return jsonify(get_published_exams())

@exam_bp.route('/<eid>', methods=['GET'])
@require_auth
def get_one(eid):
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if g.role=='student' and exam.get('status')!='published': return jsonify({'error':'Not available'}),403
    return jsonify(exam)

@exam_bp.route('/', methods=['POST'])
@require_auth
@require_teacher
def create():
    d = request.json or {}
    if not d.get('title') or not d.get('subject'):
        return jsonify({'error':'Title and subject required'}),400
    questions = d.get('questions',[])
    for i,q in enumerate(questions):
        q.setdefault('id', str(uuid.uuid4())[:6])
        q.setdefault('number', str(i+1))
        for j,sq in enumerate(q.get('subQuestions',[])):
            sq.setdefault('id', str(uuid.uuid4())[:6])
            sq.setdefault('number', f"{i+1}{chr(97+j)}")
    exam = create_exam({
        'title': d['title'], 'subject': d['subject'],
        'duration': d.get('duration',60),
        'totalMarks': d.get('totalMarks',100),
        'instructions': d.get('instructions',''),
        'questions': questions,
        'teacherId': g.uid, 'teacherName': g.user.get('name',''),
        'referenceFile': None,
        'referenceAnswers': [],
        'gradingMode': d.get('gradingMode','manual'),  # 'manual' or 'reference'
        'status': d.get('status','draft'),
    })
    return jsonify(exam),201

@exam_bp.route('/<eid>', methods=['PUT'])
@require_auth
@require_teacher
def update(eid):
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    d = request.json or {}
    allowed_fields = ['title','subject','duration','totalMarks','instructions','questions','status','gradingMode']
    updates = {k:d[k] for k in allowed_fields if k in d}
    return jsonify(update_exam(eid, updates))

@exam_bp.route('/<eid>/publish', methods=['POST'])
@require_auth
@require_teacher
def publish(eid):
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    return jsonify(update_exam(eid, {'status':'published'}))

@exam_bp.route('/<eid>', methods=['DELETE'])
@require_auth
@require_teacher
def remove(eid):
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    delete_exam(eid)
    return jsonify({'message':'Deleted'})

# ── Upload reference answer paper ──
@exam_bp.route('/<eid>/reference', methods=['POST'])
@require_auth
@require_teacher
def upload_reference(eid):
    """
    Teacher uploads ONE perfect answer paper.
    Gemini extracts Q&A from it → becomes the reference for grading all students.
    """
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    if 'file' not in request.files: return jsonify({'error':'No file'}),400
    f = request.files['file']
    if not allowed(f.filename): return jsonify({'error':'Invalid file type'}),400

    fname = f"{eid}_{uuid.uuid4().hex[:6]}.{f.filename.rsplit('.',1)[1].lower()}"
    path = os.path.join(UPLOAD_DIR, fname)
    f.save(path)

    # Extract Q&A using Gemini with enhanced v1/retry reliability
    from ml.gemini_service import extract_questions_from_paper, extract_text_from_pdf, extract_text_from_pptx
    try:
        extracted = extract_questions_from_paper(path)
        if not extracted:
            return jsonify({'error': 'AI failed to extract questions. Please check the paper or your Gemini key.'}), 400
    except Exception as e:
        return jsonify({'error': f'Gemini Error: {str(e)}'}), 400

    updates = {
        'referenceFile': fname,
        'referenceAnswers': extracted,
        'gradingMode': 'reference'
    }

    # If exam has no questions (reference-only flow), populate them
    if not exam.get('questions') or len(exam.get('questions')) == 0:
        print(f"DEBUG: Exam {eid} has no questions, syncing {len(extracted)} from reference paper")
        converted_questions = []
        total_marks = 0
        for i, ex_q in enumerate(extracted):
            # Ensure marks is a number
            try: m = float(ex_q.get('marks', 0))
            except: m = 5.0
            
            total_marks += m
            converted_questions.append({
                'id': uuid.uuid4().hex[:6],
                'number': ex_q.get('number', str(i+1)),
                'text': ex_q.get('text', f"Question {i+1}"),
                'marks': m,
                'modelAnswer': ex_q.get('answerText', ''),
                'keywords': ex_q.get('keywords', []),
                'hasDiagram': ex_q.get('hasDiagram', False),
                'subQuestions': []
            })
        updates['questions'] = converted_questions
        updates['totalMarks'] = total_marks
    else:
        # If questions exist, try to match reference answers to them
        print(f"DEBUG: Exam {eid} already has questions, matching reference answers only")

    updated_exam = update_exam(eid, updates)
    return jsonify({
        'message': f'Processed {len(extracted)} questions from reference paper',
        'questions': updated_exam.get('questions', []),
        'totalMarks': updated_exam.get('totalMarks', 0),
        'file': fname
    })

# ── Upload Study Material / Reference Content ──
@exam_bp.route('/<eid>/material', methods=['POST'])
@require_auth
@require_teacher
def upload_material(eid):
    """
    Teacher uploads study material (PDF, PPT, TXT).
    Extracted text is stored in the exam to guide AI grading.
    """
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    if 'file' not in request.files: return jsonify({'error':'No file'}),400
    
    f = request.files['file']
    ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else ''
    if ext not in {'pdf', 'pptx', 'ppt', 'txt'}:
        return jsonify({'error': 'Unsupported file type. Use PDF, PPTX, or TXT.'}), 400

    fname = f"material_{eid}_{uuid.uuid4().hex[:4]}.{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    f.save(path)

    from ml.gemini_service import extract_text_from_pdf, extract_text_from_pptx
    text = ""
    if ext == 'pdf':
        text = extract_text_from_pdf(path)
    elif ext in {'pptx', 'ppt'}:
        text = extract_text_from_pptx(path)
    elif ext == 'txt':
        with open(path, 'r', encoding='utf-8', errors='ignore') as tf:
            text = tf.read()

    if not text:
        return jsonify({'error': 'Failed to extract text from file or file is empty.'}), 400

    # Append to studyMaterial list
    materials = exam.get('studyMaterial', [])
    materials.append({
        'id': uuid.uuid4().hex[:4],
        'filename': f.filename,
        'storageName': fname,
        'text': text[:50000] # Limit to 50k chars per file to save space, AI usually doesn't need more for context
    })
    
    update_exam(eid, {'studyMaterial': materials})
    return jsonify({
        'message': f'Material "{f.filename}" uploaded and processed.',
        'materials': [{'id': m['id'], 'filename': m['filename']} for m in materials]
    })

@exam_bp.route('/<eid>/material/<mid>', methods=['DELETE'])
@require_auth
@require_teacher
def delete_material(eid, mid):
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    
    materials = exam.get('studyMaterial', [])
    new_materials = [m for m in materials if m['id'] != mid]
    if len(new_materials) == len(materials):
        return jsonify({'error': 'Material not found'}), 404
        
    update_exam(eid, {'studyMaterial': new_materials})
    return jsonify({'message': 'Material removed'})

# ── Extract Questions from Blank Paper ──
@exam_bp.route('/<eid>/extract-questions', methods=['POST'])
@require_auth
@require_teacher
def extract_questions_route(eid):
    """
    Teacher uploads a BLANK question paper.
    Gemini extracts the structure (number, text, marks).
    """
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    if 'file' not in request.files: return jsonify({'error':'No file'}),400
    
    f = request.files['file']
    if not allowed(f.filename): return jsonify({'error':'Invalid file type'}),400

    fname = f"qpaper_{eid}_{uuid.uuid4().hex[:6]}.{f.filename.rsplit('.',1)[1].lower()}"
    path = os.path.join(UPLOAD_DIR, fname)
    f.save(path)

    from ml.gemini_service import extract_paper_structure
    try:
        extracted = extract_paper_structure(path)
        if not extracted:
            return jsonify({'error': 'AI failed to extract questions. Please check the paper.'}), 400
        
        # Convert to exam questions format
        converted = []
        total_m = 0
        for i, q in enumerate(extracted):
            m = float(q.get('marks', 5.0))
            total_m += m
            converted.append({
                'id': uuid.uuid4().hex[:6],
                'number': q.get('number', str(i+1)),
                'text': q.get('text', ''),
                'marks': m,
                'modelAnswer': '',
                'keywords': [],
                'subQuestions': []
            })
        
        update_exam(eid, {'questions': converted, 'totalMarks': total_m})
        return jsonify({
            'message': f'Extracted {len(converted)} questions.',
            'questions': converted,
            'totalMarks': total_m
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Generate Answers for Questions ──
@exam_bp.route('/<eid>/generate-answers', methods=['POST'])
@require_auth
@require_teacher
def generate_answers_route(eid):
    """
    Generates model answers and rubrics for existing questions.
    Modes: 'general' (training data) or 'material' (uploaded PDFs/PPTs).
    """
    exam = get_exam(eid)
    if not exam: return jsonify({'error':'Not found'}),404
    if exam.get('teacherId') != g.uid: return jsonify({'error':'Not yours'}),403
    
    questions = exam.get('questions', [])
    if not questions:
        return jsonify({'error': 'No questions to generate answers for. Upload a paper or add questions manually first.'}), 400
    
    d = request.json or {}
    mode = d.get('mode', 'general') # 'general' or 'material'
    
    study_material_text = None
    if mode == 'material':
        materials = exam.get('studyMaterial', [])
        if not materials:
            return jsonify({'error': 'No study materials found. Please upload PPTs or PDFs first.'}), 400
        study_material_text = "\n\n".join([m.get('text', '') for m in materials])

    from ml.gemini_service import enrich_questions_with_answers
    try:
        # Prepare for AI (simpler format)
        ai_input = []
        for q in questions:
            ai_input.append({'number': q['number'], 'text': q['text'], 'marks': q['marks']})
        
        enriched = enrich_questions_with_answers(ai_input, subject_hint=exam.get('subject', ''), study_material=study_material_text)
        
        # Merge back
        for eq in enriched:
            # Find matching question in original list
            q = next((x for x in questions if x['number'] == eq['number']), None)
            if q:
                q['modelAnswer'] = eq.get('answerText', '')
                q['assessmentParameters'] = eq.get('assessmentParameters', [])
                q['relevantSources'] = eq.get('relevantSources', [])
                q['researchContext'] = eq.get('researchContext', '')
                q['hasDiagram'] = eq.get('hasDiagram', False)
                # Handle keywords if generated (Gemini usually generates them in text sometimes)
                if not q.get('keywords'):
                    q['keywords'] = eq.get('relevantSources', [])[:3]

        update_exam(eid, {'questions': questions})
        return jsonify({
            'message': 'Answers generated successfully.',
            'questions': questions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@exam_bp.route('/<eid>/submissions', methods=['GET'])
@require_auth
@require_teacher
def exam_subs(eid):
    exam = get_exam(eid)
    if not exam or exam.get('teacherId') != g.uid:
        return jsonify({'error':'Not found'}),404
    subs = get_exam_submissions(eid)
    return jsonify(subs)
