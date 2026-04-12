# 🎓 AutoGrader — Setup Guide

## Run in 3 commands
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
python app.py               # starts on :5000

# Second terminal:
cd frontend
python -m http.server 8080  # open http://localhost:8080
```

---

## Get Gemini API Key (Free)
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API key"
3. Copy it → paste in `backend/.env` as `GEMINI_API_KEY=...`

---

## Demo Accounts
| Role | Email | Password |
|------|-------|----------|
| Teacher | teacher@demo.com | demo123 |
| Student | student@demo.com | demo123 |

---

## 3 USPs

### USP 1: Reference Paper Grading
Teacher uploads ONE perfect answer paper → Gemini extracts Q&A →
all student sheets graded against it automatically with SBERT similarity.
No manual model answer entry needed.

### USP 2: Diagram Extraction + SSIM
OpenCV contour detection finds diagram regions in answer sheets.
Compares student diagrams to reference using Structural Similarity Index.
First automated diagram comparison in exam grading.

### USP 3: Answer Cluster Heatmap
KMeans clusters student answers per question.
Heatmap shows class performance patterns — teacher sees which questions
entire class failed (curriculum gap) vs individual failures (student gap).

---

## ML Models Visible
- **Sentence-BERT** (all-MiniLM-L6-v2) — 40% weight — semantic cosine similarity
- **TF-IDF Cosine** (sklearn) — 25% weight — vocabulary overlap
- **ROUGE-L** (LCS) — 20% weight — sequence matching
- **Keyword BM25** — 15% weight — expected term coverage
- **OpenCV SSIM** — diagram structural comparison
- **KMeans** (sklearn) — answer cluster analysis
- **Gemini 1.5 Flash** — OCR + feedback generation

---

## Troubleshooting
- `Cannot connect to backend` → run `python app.py` in backend/
- `GEMINI_API_KEY not set` → copy .env.example to .env and add key
- `sentence-transformers slow` → first run downloads ~90MB model
- CORS error → serve frontend with `python -m http.server`, not file://
- `torch install fails` → `pip install torch --index-url https://download.pytorch.org/whl/cpu`
