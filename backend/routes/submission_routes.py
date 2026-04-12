"""Submission Routes — full ML grading pipeline"""
import os, uuid, io
from flask import Blueprint, request, jsonify, g, send_file
from werkzeug.utils import secure_filename
from utils.local_db import (create_submission, get_submission, update_submission,
                             get_student_submissions, get_exam_submissions, get_exam, get_user)
from utils.auth import require_auth, require_teacher, require_student
from ml.engine import ensemble_score, extract_diagrams_from_image, diagram_similarity, compute_percentile, detect_weaknesses
from ml.gemini_service import extract_answer_sheet, grade_answer_feedback, generate_student_report
from ml.report_gen import generate_report

sub_bp = Blueprint('submissions', __name__)
SUB_DIR = os.path.join(os.path.dirname(__file__),'..','uploads','submissions')
REP_DIR = os.path.join(os.path.dirname(__file__),'..','uploads','reports')
REF_DIR = os.path.join(os.path.dirname(__file__),'..','uploads','reference')
ALLOWED = {'pdf','png','jpg','jpeg','webp'}

def allowed(fn): return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

@sub_bp.route('/', methods=['GET'])
@require_auth
def list_subs():
    if g.role == 'student':
        return jsonify(get_student_submissions(g.uid))
    # Teacher: filter by examId if provided
    exam_id = request.args.get('examId')
    if exam_id:
        exam = get_exam(exam_id)
        if exam and exam.get('teacherId') == g.uid:
            return jsonify(get_exam_submissions(exam_id))
        return jsonify([])
        
    from utils.local_db import get_exams
    exams = get_exams()
    subs = []
    for eid, e in exams.items():
        if e.get('teacherId') == g.uid:
            subs.extend(get_exam_submissions(eid))
            
    subs.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    return jsonify(subs)

@sub_bp.route('/<sid>', methods=['GET'])
@require_auth
def get_one(sid):
    s = get_submission(sid)
    if not s: return jsonify({'error':'Not found'}),404
    if g.role=='student' and s.get('studentId')!=g.uid: return jsonify({'error':'Access denied'}),403
    return jsonify(s)

@sub_bp.route('/upload', methods=['POST'])
@require_auth
def upload_and_grade():
    """
    Main grading endpoint:
    1. Save uploaded answer sheet
    2. Gemini OCR extracts answers (handles random order)
    3. ML ensemble scores each answer vs reference
    4. Diagram extraction + SSIM comparison
    5. Gemini generates feedback per question
    6. Save + return graded submission
    """
    exam_id = request.form.get('examId')
    student_name = request.form.get('studentName', '').strip()
    if not exam_id: return jsonify({'error':'examId required'}),400

    exam = get_exam(exam_id)
    if not exam: return jsonify({'error':'Exam not found'}),404

    # Determine student
    if g.role == 'student':
        student_id = g.uid
        student_name = g.user.get('name','')
    else:
        # Try to find the student by name to link the submission to their account
        from utils.local_db import get_users
        found_student = next((u for u in get_users().values() if u.get('role') == 'student' and u.get('name', '').lower() == student_name.lower()), None)
        if found_student:
            student_id = found_student['id']
            student_name = found_student['name'] # Use exact casing from DB
        else:
            student_id = f"manual_{uuid.uuid4().hex[:4]}"

    # Save file
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}),400
    f = request.files['file']
    if not allowed(f.filename): return jsonify({'error':'Invalid file type'}),400
    fname = f"{uuid.uuid4().hex[:8]}.{f.filename.rsplit('.',1)[1].lower()}"
    fpath = os.path.join(SUB_DIR, fname)
    f.save(fpath)

    # Get reference answers
    ref_answers = exam.get('referenceAnswers', [])
    questions = exam.get('questions', [])

    # Flatten questions (include subquestions)
    flat_questions = []
    for q in questions:
        if q.get('subQuestions'):
            flat_questions.extend(q['subQuestions'])
        else:
            flat_questions.append(q)

    # Step 1: OCR answer extraction
    from ml.gemini_service import _clean_qnum
    try:
        extracted = extract_answer_sheet(fpath, flat_questions)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
        
    # Store normalized keys for robust matching
    ans_map = {_clean_qnum(a['questionNumber']): a for a in extracted} if extracted else {}

    # Step 2: Extract diagrams from student sheet
    diag_dir = os.path.join(SUB_DIR, f"diags_{fname.split('.')[0]}")
    student_diagrams = extract_diagrams_from_image(fpath, diag_dir, prefix='student')

    # Step 3: Grade each question
    grades = []
    total_score = 0
    max_score = 0

    for q in flat_questions:
        qnum_raw = q.get('number','?')
        qnum_clean = _clean_qnum(qnum_raw)
        max_m = q.get('marks', 5)
        max_score += max_m

        # Find student answer using cleaned key
        ans_entry = ans_map.get(qnum_clean, {})
        student_ans = ans_entry.get('answerText','') if ans_entry else ''

        # Find reference answer - use cleaned IDs for robust matching
        ref_entry = next((r for r in ref_answers if _clean_qnum(r.get('number')) == qnum_clean), {})
        ref_ans = ref_entry.get('answerText', q.get('modelAnswer',''))
        keywords = q.get('keywords', [])

        # ML Ensemble score
        ml = ensemble_score(student_ans, ref_ans, keywords)
        ml_score = ml['final']

        # Diagram comparison if needed
        diag_score = None
        if q.get('hasDiagram') and student_diagrams:
            ref_diag = ref_entry.get('diagramPath','')
            if ref_diag and os.path.exists(os.path.join(REF_DIR, ref_diag)):
                best = max([diagram_similarity(d['path'], os.path.join(REF_DIR, ref_diag))
                            for d in student_diagrams], default=0)
                diag_score = best
                ml_score = ml_score * 0.7 + diag_score * 0.3

        # Gemini feedback (Higher Weight for qualitative context)
        # Note: Suggested score is now 0-100 from Gemini
        feedback_data = grade_answer_feedback(
            q.get('text',''), ref_ans, student_ans, max_m or 5, ml_score)

        # gemini_pct is returned as 0-100. Fallback to ml_score directly because ml_score is already 0-100.
        gemini_pct = float(feedback_data.get('suggestedScore', ml_score))
        
        # Weight AI higher (80%) and ML (20%) for a balanced assessment without extra multipliers
        final_pct = min(100, max(0, (ml_score * 0.20 + gemini_pct * 0.80)))
        # Marks awarded calculation - more lenient rounding to match "Teacher Sentiment"
        # If the student is at least 30% of the way to the next mark, round UP.
        raw_marks = (final_pct / 100 * float(max_m or 5))
        marks_awarded = int(raw_marks)
        if raw_marks - marks_awarded >= 0.3:
            marks_awarded += 1
        marks_awarded = min(marks_awarded, max_m)
        total_score += marks_awarded

        grades.append({
            'questionNumber': qnum_raw,
            'questionText': q.get('text','')[:120],
            'studentAnswer': student_ans,
            'marks': marks_awarded,
            'maxMarks': max_m or 5,
            'percentage': round(final_pct, 1),
            'feedback': feedback_data.get('feedback',''),
            'strengths': feedback_data.get('strengths',[]),
            'mistakes': feedback_data.get('mistakes',[]),
            'improvements': feedback_data.get('improvements',[]),
            'hasDiagram': bool(ans_entry.get('hasDiagram')),
            'diagramScore': diag_score,
            'breakdown': {k:v for k,v in ml.items() if k not in ('final','model')},
        })

    overall_pct = round(total_score / max_score * 100, 1) if max_score > 0 else 0

    # "5 Marks Pass" Logic (User Request)
    status_label = "PASS" if total_score >= 5.0 else "FAIL"

    # Narrative
    narrative = generate_student_report(student_name, exam.get('title',''), grades, overall_pct)

    sub = create_submission({
        'examId': exam_id,
        'examTitle': exam.get('title',''),
        'studentId': student_id,
        'studentName': student_name,
        'answerSheetFile': fname,
        'originalFilename': f.filename,
        'grades': grades,
        'totalScore': round(total_score,1),
        'maxScore': max_score,
        'percentage': overall_pct,
        'mlScore': overall_pct,
        'result': status_label,
        'narrative': narrative,
        'status': 'graded',
        'gradedAt': __import__('utils.local_db', fromlist=['now']).now(),
    })

    return jsonify(sub)

@sub_bp.route('/<sid>/override', methods=['PATCH'])
@require_auth
@require_teacher
def override(sid):
    s = get_submission(sid)
    if not s: return jsonify({'error':'Not found'}),404
    d = request.json or {}
    q_idx = d.get('questionIndex')
    new_marks = float(d.get('marks',0))
    note = d.get('note','')
    grades = s.get('grades',[])
    if q_idx is None or q_idx >= len(grades): return jsonify({'error':'Invalid index'}),400
    g_item = grades[q_idx]
    g_item['marks'] = max(0, min(new_marks, g_item['maxMarks']))
    g_item['percentage'] = round(g_item['marks']/g_item['maxMarks']*100,1) if g_item['maxMarks'] else 0
    g_item['overridden'] = True; g_item['overrideNote'] = note
    if note: g_item['feedback'] = f'[Teacher Override: {note}] ' + g_item.get('feedback','')
    total = sum(g['marks'] for g in grades)
    max_s = sum(g['maxMarks'] for g in grades)
    pct = round(total/max_s*100,1) if max_s else 0
    updated = update_submission(sid, {'grades':grades,'totalScore':round(total,1),'percentage':pct,'teacherScore':pct})
    return jsonify(updated)

@sub_bp.route('/<sid>/report', methods=['GET'])
@require_auth
def download_report(sid):
    s = get_submission(sid)
    if not s: return jsonify({'error':'Not found'}),404
    if g.role=='student' and s.get('studentId')!=g.uid: return jsonify({'error':'Access denied'}),403
    exam = get_exam(s.get('examId','')) or {}
    pdf_bytes = generate_report(s, exam, s.get('studentName','Student'), s.get('narrative',''))
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True,
                     download_name=f"report_{s.get('studentName','student').replace(' ','_')}.pdf")

@sub_bp.route('/<sid>', methods=['DELETE'])
@require_auth
def delete_sub(sid):
    from utils.local_db import delete_submission
    s = get_submission(sid)
    if not s: return jsonify({'error':'Not found'}),404
    # Security: Only owner or teacher can delete
    if g.role == 'student' and s.get('studentId') != g.uid:
        return jsonify({'error':'Unauthorized'}),403
    
    # Optional: Delete physical file
    fname = s.get('answerSheetFile')
    if fname:
        fpath = os.path.join(SUB_DIR, fname)
        if os.path.exists(fpath): 
            try: os.remove(fpath)
            except: pass
            
    delete_submission(sid)
    return jsonify({'success':True})
