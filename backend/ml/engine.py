"""
ExamAI ML Engine — All ML models in one place
Models used (visible + measurable):
  1. Sentence-BERT (all-MiniLM-L6-v2) — semantic answer similarity
  2. TF-IDF + Cosine Similarity       — vocabulary overlap scoring
  3. ROUGE-L                          — sequence-based answer matching
  4. OpenCV SSIM                      — diagram structural similarity
  5. Sklearn KMeans                   — answer cluster analysis
"""

import re, math, os
import numpy as np
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
from scipy.stats import percentileofscore

# ── Lazy load heavy model ──
_sbert = None
def get_sbert():
    global _sbert
    if _sbert is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading Sentence-BERT (all-MiniLM-L6-v2)...")
            _sbert = SentenceTransformer('all-MiniLM-L6-v2')
            print("✅ Sentence-BERT loaded")
        except Exception as e:
            print(f"⚠ SBERT unavailable: {e}")
            _sbert = 'unavailable'
    return _sbert if _sbert != 'unavailable' else None

STOP = {'the','a','an','is','are','was','were','be','been','have','has','do','does',
        'not','but','or','and','to','of','in','on','at','by','for','with','as',
        'this','that','it','its','they','we','you','i','me','my','your','our'}

def tokenize(t):
    return [w for w in re.sub(r'[^\w\s]',' ',t.lower()).split() if len(w)>2 and w not in STOP]

# ── Model 1: Sentence-BERT Semantic Similarity ──
def sbert_similarity(a, b):
    """Returns cosine similarity score 0-100 using Sentence-BERT embeddings"""
    model = get_sbert()
    if not model or not a.strip() or not b.strip():
        return tfidf_similarity(a, b)  # fallback
    try:
        embs = model.encode([a, b])
        score = float(np.dot(embs[0], embs[1]) /
                      (np.linalg.norm(embs[0]) * np.linalg.norm(embs[1]) + 1e-9))
        return max(0, min(100, score * 100))
    except:
        return tfidf_similarity(a, b)

# ── Model 2: TF-IDF Cosine Similarity ──
def tfidf_similarity(a, b):
    """Returns TF-IDF cosine similarity 0-100"""
    if not a.strip() or not b.strip(): return 0.0
    try:
        vec = TfidfVectorizer(stop_words='english', ngram_range=(1,2))
        mat = vec.fit_transform([a, b])
        score = float(cosine_similarity(mat[0], mat[1])[0][0])
        return max(0, min(100, score * 100))
    except:
        return jaccard(a, b)

def jaccard(a, b):
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa or not sb: return 0.0
    return 100 * len(sa & sb) / len(sa | sb)

# ── Model 3: ROUGE-L (LCS-based) ──
def rouge_l(hyp, ref):
    """ROUGE-L F1 score 0-100"""
    h, r = tokenize(hyp)[:80], tokenize(ref)[:80]
    if not h or not r: return 0.0
    dp = [[0]*(len(r)+1) for _ in range(len(h)+1)]
    for i in range(1,len(h)+1):
        for j in range(1,len(r)+1):
            dp[i][j] = dp[i-1][j-1]+1 if h[i-1]==r[j-1] else max(dp[i-1][j],dp[i][j-1])
    lcs = dp[len(h)][len(r)]
    p = lcs/len(h) if h else 0
    rc = lcs/len(r) if r else 0
    f1 = 2*p*rc/(p+rc) if p+rc else 0
    return round(f1 * 100, 1)

# ── Keyword Coverage ──
def keyword_coverage(text, keywords):
    """% of expected keywords found in text"""
    if not keywords: return 50.0
    found = sum(1 for k in keywords if k.lower() in text.lower())
    return round(found / len(keywords) * 100, 1)

# ── Ensemble Score ──
def ensemble_score(student_ans, ref_ans, keywords=None, weights=None):
    """
    Final score = weighted ensemble of:
      SBERT(40%) + TF-IDF(25%) + ROUGE-L(20%) + Keywords(15%)
    Returns dict with individual scores + final
    """
    if not student_ans.strip():
        return {'sbert':0,'tfidf':0,'rouge_l':0,'keywords':0,'final':0,'model':'ensemble'}

    sb  = sbert_similarity(student_ans, ref_ans)
    tf  = tfidf_similarity(student_ans, ref_ans)
    rl  = rouge_l(student_ans, ref_ans)
    kw  = keyword_coverage(student_ans, keywords or [])

    w = weights or {'sbert':0.60,'tfidf':0.20,'rouge_l':0.10,'keywords':0.10}
    final = w['sbert']*sb + w['tfidf']*tf + w['rouge_l']*rl + w['keywords']*kw

    return {
        'sbert': round(sb,1), 'tfidf': round(tf,1),
        'rouge_l': round(rl,1), 'keywords': round(kw,1),
        'final': round(final,1), 'model': 'SBERT+TF-IDF+ROUGE-L+Keywords'
    }

# ── Model 4: Diagram Similarity (OpenCV SSIM) ──
def diagram_similarity(img_a_path, img_b_path):
    """
    Structural Similarity Index (SSIM) between two diagram images.
    Returns 0-100.
    """
    try:
        import cv2
        from skimage.metrics import structural_similarity as ssim
        a = cv2.imread(img_a_path, cv2.IMREAD_GRAYSCALE)
        b = cv2.imread(img_b_path, cv2.IMREAD_GRAYSCALE)
        if a is None or b is None: return 0.0
        h = min(a.shape[0], b.shape[0], 400)
        w = min(a.shape[1], b.shape[1], 400)
        a = cv2.resize(a, (w, h))
        b = cv2.resize(b, (w, h))
        score, _ = ssim(a, b, full=True)
        return round(max(0, score) * 100, 1)
    except Exception as e:
        print(f"Diagram SSIM error: {e}")
        return 0.0

def extract_diagrams_from_image(img_path, out_dir, prefix='diag'):
    """
    Uses OpenCV contour detection to extract diagram regions from answer sheet.
    Returns list of saved diagram paths.
    """
    try:
        import cv2
        img = cv2.imread(img_path)
        if img is None: return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Edge detection
        blurred = cv2.GaussianBlur(gray, (5,5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        os.makedirs(out_dir, exist_ok=True)
        saved = []
        H, W = img.shape[:2]
        min_area = H * W * 0.02  # At least 2% of image
        for i, cnt in enumerate(contours):
            x,y,w,h = cv2.boundingRect(cnt)
            area = w * h
            aspect = w / max(h, 1)
            # Diagrams: large enough, roughly square-ish
            if area > min_area and 0.3 < aspect < 3.5 and w > 60 and h > 60:
                roi = img[y:y+h, x:x+w]
                path = os.path.join(out_dir, f'{prefix}_diag_{i}.png')
                cv2.imwrite(path, roi)
                saved.append({'path': path, 'x':x,'y':y,'w':w,'h':h,'area':area})
        return saved
    except Exception as e:
        print(f"Diagram extraction error: {e}")
        return []

# ── Model 5: KMeans Answer Clustering ──
def cluster_answers(answers_dict, n_clusters=3):
    """
    Groups student answers by similarity using KMeans on TF-IDF vectors.
    answers_dict: {student_id: answer_text}
    Returns cluster labels per student
    """
    if len(answers_dict) < 3:
        return {k: 0 for k in answers_dict}
    try:
        ids = list(answers_dict.keys())
        texts = [answers_dict[k] for k in ids]
        vec = TfidfVectorizer(stop_words='english', max_features=200)
        X = vec.fit_transform(texts).toarray()
        k = min(n_clusters, len(ids))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        return {ids[i]: int(labels[i]) for i in range(len(ids))}
    except:
        return {k: 0 for k in answers_dict}

# ── Performance Percentile ──
def compute_percentile(score, all_scores):
    if not all_scores: return 50
    return round(percentileofscore(all_scores, score, kind='rank'))

# ── Weakness Detection ──
def detect_weaknesses(grades):
    """
    Given list of {qLabel, marks, maxMarks, percentage},
    returns list of weak questions (below 50%)
    """
    return [g for g in grades if g.get('percentage', 100) < 50]

def accuracy_report(all_submissions):
    """
    Computes model accuracy metrics across all submissions.
    Compares ML-predicted grade vs teacher-overridden grade (if any).
    """
    pairs = [(s['mlScore'], s.get('teacherScore', s['mlScore']))
             for s in all_submissions
             if 'mlScore' in s and s.get('status') == 'graded']
    if not pairs:
        return {'mae': None, 'samples': 0}
    ml_scores = [p[0] for p in pairs]
    teacher_scores = [p[1] for p in pairs]
    mae = float(np.mean(np.abs(np.array(ml_scores) - np.array(teacher_scores))))
    corr = float(np.corrcoef(ml_scores, teacher_scores)[0,1]) if len(pairs) > 1 else 1.0
    return {
        'mae': round(mae, 2),
        'correlation': round(corr, 3),
        'samples': len(pairs),
        'avg_ml': round(float(np.mean(ml_scores)), 1),
        'avg_teacher': round(float(np.mean(teacher_scores)), 1)
    }
