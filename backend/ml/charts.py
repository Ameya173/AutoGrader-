"""
Chart Generator — matplotlib/seaborn charts
All charts saved as PNG, served as static files
"""
import os, io, base64
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

PALETTE = ['#2563EB','#059669','#D97706','#DC2626','#7C3AED','#0891B2']
BG = '#0D1117'; GRID = '#1E293B'; TEXT = '#94A3B8'

def _style(ax, title=''):
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT, labelsize=8)
    for spine in ax.spines.values(): spine.set_edgecolor(GRID)
    ax.xaxis.label.set_color(TEXT); ax.yaxis.label.set_color(TEXT)
    if title: ax.set_title(title, color='#E2E8F0', fontsize=10, fontweight='bold', pad=8)
    ax.grid(True, color=GRID, alpha=0.7, linewidth=0.5)

def _to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor=BG, dpi=120)
    buf.seek(0)
    data = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return data

# ── 1. Grade Distribution Bar Chart ──
def grade_distribution(submissions):
    """Bar chart of grade distribution A+/A/B/C/D/F"""
    dist = {'A+':0,'A':0,'B':0,'C':0,'D':0,'F':0}
    for s in submissions:
        p = s.get('percentage',0)
        if p>=90: dist['A+']+=1
        elif p>=80: dist['A']+=1
        elif p>=70: dist['B']+=1
        elif p>=60: dist['C']+=1
        elif p>=50: dist['D']+=1
        else: dist['F']+=1

    fig, ax = plt.subplots(figsize=(7,3.5))
    fig.patch.set_facecolor(BG)
    colors = ['#059669','#059669','#2563EB','#D97706','#F97316','#DC2626']
    bars = ax.bar(list(dist.keys()), list(dist.values()), color=colors, width=0.6)
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x()+bar.get_width()/2, h+0.1, str(int(h)),
                    ha='center', va='bottom', color='#E2E8F0', fontsize=9, fontweight='bold')
    _style(ax, 'Grade Distribution')
    ax.set_xlabel('Grade'); ax.set_ylabel('Students')
    return _to_b64(fig)

# ── 2. Question-wise Performance Heatmap (USP) ──
def question_performance_heatmap(submissions, questions):
    """
    USP: Heatmap where each cell = student × question score.
    Shows class performance patterns at a glance.
    """
    if len(submissions) < 2 or not questions: return None
    names = [s.get('studentName','?')[:10] for s in submissions]
    q_nums = [q.get('number','?') for q in questions]

    matrix = []
    for s in submissions:
        row = []
        grades_map = {g['questionNumber']: g.get('percentage',0) for g in s.get('grades',[])}
        for q in questions:
            row.append(grades_map.get(q.get('number',''),0))
        matrix.append(row)

    if not matrix: return None
    arr = np.array(matrix, dtype=float)
    fig, ax = plt.subplots(figsize=(max(6, len(q_nums)*0.8), max(3.5, len(names)*0.45)))
    fig.patch.set_facecolor(BG)
    cmap = sns.color_palette("RdYlGn", as_cmap=True)
    sns.heatmap(arr, annot=True, fmt='.0f', cmap=cmap,
                xticklabels=[f'Q{n}' for n in q_nums],
                yticklabels=names,
                vmin=0, vmax=100,
                ax=ax, linewidths=0.3, linecolor=GRID,
                cbar_kws={'label': 'Score %', 'shrink': 0.8},
                annot_kws={'size': 8})
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT, labelsize=8)
    ax.set_title('Question × Student Performance Heatmap', color='#E2E8F0', fontsize=10, fontweight='bold', pad=10)
    fig.tight_layout()
    return _to_b64(fig)

# ── 3. Score Distribution Histogram ──
def score_histogram(submissions):
    """Histogram of student scores"""
    scores = [s.get('percentage',0) for s in submissions if s.get('status')=='graded']
    if not scores: return None
    fig, ax = plt.subplots(figsize=(6,3))
    fig.patch.set_facecolor(BG)
    ax.hist(scores, bins=10, range=(0,100), color='#2563EB', edgecolor=GRID, alpha=0.85)
    ax.axvline(np.mean(scores), color='#D97706', linestyle='--', linewidth=1.5, label=f'Avg: {np.mean(scores):.1f}%')
    ax.axvline(50, color='#DC2626', linestyle=':', linewidth=1, label='Pass (50%)')
    ax.legend(fontsize=8, labelcolor=TEXT)
    _style(ax, 'Score Distribution')
    ax.set_xlabel('Score (%)'); ax.set_ylabel('Count')
    return _to_b64(fig)

# ── 4. ML Model Score Breakdown (radar/bar) — shows each model's contribution ──
def ml_breakdown_chart(breakdown_data):
    """
    Bar chart showing individual ML model scores for one submission.
    breakdown_data = {'sbert': 72, 'tfidf': 68, 'rouge_l': 65, 'keywords': 80}
    """
    if not breakdown_data: return None
    fig, ax = plt.subplots(figsize=(5.5,3))
    fig.patch.set_facecolor(BG)
    labels = list(breakdown_data.keys())
    values = [breakdown_data[k] for k in labels]
    label_map = {'sbert':'SBERT','tfidf':'TF-IDF','rouge_l':'ROUGE-L','keywords':'Keywords'}
    bars = ax.barh([label_map.get(l,l) for l in labels], values,
                   color=PALETTE[:len(labels)], height=0.5)
    for bar, val in zip(bars, values):
        ax.text(val+1, bar.get_y()+bar.get_height()/2, f'{val:.0f}%',
                va='center', color='#E2E8F0', fontsize=9)
    ax.set_xlim(0, 110)
    _style(ax, 'ML Model Scores')
    ax.set_xlabel('Score (%)')
    return _to_b64(fig)

# ── 5. Student's per-question radar chart ──
def student_radar(grades, student_name):
    """Radar/spider chart of student's per-question performance"""
    if len(grades) < 3: return None
    labels = [f"Q{g.get('questionNumber','?')}" for g in grades]
    values = [g.get('percentage',0) for g in grades]
    N = len(labels)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    values += values[:1]

    fig, ax = plt.subplots(figsize=(4.5,4.5), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.plot(angles, values, 'o-', linewidth=2, color='#2563EB')
    ax.fill(angles, values, alpha=0.2, color='#2563EB')
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels, color=TEXT, fontsize=8)
    ax.set_ylim(0,100); ax.set_yticklabels(['20','40','60','80','100'], color=TEXT, fontsize=7)
    ax.grid(color=GRID, linewidth=0.5)
    ax.set_title(f'{student_name[:20]} — Performance Radar', color='#E2E8F0', fontsize=9, pad=15)
    fig.tight_layout()
    return _to_b64(fig)

# ── 6. Cluster visualization ──
def cluster_chart(cluster_labels, student_names, avg_scores):
    """Scatter: x=avg_score, y=student_index, colored by cluster"""
    if not cluster_labels: return None
    fig, ax = plt.subplots(figsize=(6,3.5))
    fig.patch.set_facecolor(BG)
    cluster_colors = {0:'#2563EB',1:'#059669',2:'#D97706',3:'#DC2626'}
    for name, score, cluster in zip(student_names, avg_scores, cluster_labels.values()):
        ax.scatter(score, 0, c=cluster_colors.get(cluster,'#7C3AED'), s=80, zorder=3)
    for c, col in cluster_colors.items():
        ax.scatter([], [], c=col, label=f'Group {c+1}')
    ax.legend(fontsize=8, labelcolor=TEXT)
    _style(ax, 'Student Answer Clusters (KMeans)')
    ax.set_xlabel('Average Score (%)'); ax.set_yticks([])
    return _to_b64(fig)
