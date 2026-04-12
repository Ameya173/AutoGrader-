"""Analytics Routes — charts + ML accuracy metrics"""
from flask import Blueprint, jsonify, request, g
from utils.local_db import get_exam, get_exam_submissions, get_student_submissions
from utils.auth import require_auth, require_teacher
from ml.engine import cluster_answers, compute_percentile, detect_weaknesses, accuracy_report
from ml.charts import (grade_distribution, question_performance_heatmap,
                        score_histogram, ml_breakdown_chart, student_radar, cluster_chart)

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/exam/<eid>', methods=['GET'])
@require_auth
@require_teacher
def exam_analytics(eid):
    exam = get_exam(eid)
    if not exam or exam.get('teacherId') != g.uid:
        return jsonify({'error':'Not found'}),404

    subs = [s for s in get_exam_submissions(eid) if s.get('status')=='graded']
    if not subs:
        return jsonify({'message':'No graded submissions yet','charts':{}})

    scores = [s.get('percentage',0) for s in subs]
    avg = round(sum(scores)/len(scores),1) if scores else 0
    passed = sum(1 for s in scores if s >= 50)

    # Generate charts
    charts = {}
    charts['grade_distribution'] = grade_distribution(subs)
    charts['score_histogram'] = score_histogram(subs)

    q_flat = []
    for q in exam.get('questions',[]):
        if q.get('subQuestions'): q_flat.extend(q['subQuestions'])
        else: q_flat.append(q)
    if q_flat:
        charts['heatmap'] = question_performance_heatmap(subs, q_flat)

    # KMeans clusters for each question
    q_clusters = {}
    for q in q_flat:
        qnum = q.get('number','?')
        ans_map = {}
        for s in subs:
            gr = next((g for g in s.get('grades',[]) if g.get('questionNumber')==qnum), None)
            if gr and gr.get('studentAnswer'):
                ans_map[s.get('studentName','?')] = gr['studentAnswer']
        if len(ans_map) >= 3:
            q_clusters[f'Q{qnum}'] = cluster_answers(ans_map)

    # Per-question avg
    q_avgs = {}
    for q in q_flat:
        qnum = q.get('number','?')
        pcts = [g.get('percentage',0) for s in subs for g in s.get('grades',[]) if g.get('questionNumber')==qnum]
        q_avgs[f'Q{qnum}'] = round(sum(pcts)/len(pcts),1) if pcts else 0

    # ML model accuracy
    acc = accuracy_report(subs)

    return jsonify({
        'total': len(subs), 'avg': avg, 'passed': passed,
        'passRate': round(passed/len(subs)*100,1) if subs else 0,
        'scores': scores,
        'questionAvgs': q_avgs,
        'clusters': q_clusters,
        'mlAccuracy': acc,
        'charts': charts,
    })

@analytics_bp.route('/student', methods=['GET'])
@require_auth
def student_analytics():
    subs = [s for s in get_student_submissions(g.uid) if s.get('status')=='graded']
    if not subs:
        return jsonify({'submissions':[], 'charts':{}})

    charts = {}
    all_scores = [s.get('percentage',0) for s in subs]

    # Latest submission radar
    latest = subs[-1]
    grades = latest.get('grades',[])
    if len(grades) >= 3:
        charts['radar'] = student_radar(grades, g.user.get('name','Student'))

    # ML breakdown for latest
    if grades:
        avg_bd = {}
        for gr in grades:
            for k,v in gr.get('breakdown',{}).items():
                avg_bd[k] = avg_bd.get(k,0) + v
        n = len(grades)
        avg_bd = {k:round(v/n,1) for k,v in avg_bd.items()}
        charts['ml_breakdown'] = ml_breakdown_chart(avg_bd)

    # Weaknesses across all submissions
    all_weak = []
    for s in subs:
        all_weak.extend(detect_weaknesses(s.get('grades',[])))

    return jsonify({
        'submissions': subs,
        'totalExams': len(subs),
        'avgScore': round(sum(all_scores)/len(all_scores),1) if all_scores else 0,
        'bestScore': max(all_scores) if all_scores else 0,
        'weakQuestions': all_weak[:5],
        'charts': charts,
    })
