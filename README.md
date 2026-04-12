# 🎓 AutoGrader (ExamAI) — Complete Project Documentation

**AutoGrader (ExamAI)** is a comprehensive, production-ready AI-powered examination evaluation system designed to automate the grading of unstructured, handwritten, and diagrammatic student answer sheets. 

It eliminates the implicit bias and massive time consumption of manual grading through a highly complex **Ensemble Machine Learning Architecture** paired with **Google Gemini 1.5 Flash**.

---

## 🚀 1. Setup & Quick Start

The project runs on a Python Flask REST API backend and a Vanilla JS/HTML/CSS frontend.

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
cp .env.example .env        # Add your GEMINI_API_KEY from Google AI Studio
python app.py               # Starts on http://127.0.0.1:5000

# Terminal 2: Frontend
cd frontend
python -m http.server 8080  # Opens on http://localhost:8080
```

---

## 🏛 2. Core Architecture & Project Flow

The core architecture operates over two distinct workflows: **Test Creation** and **Paper Grading**.

### Phase 1: Test Creation (The Dual-Upload Model)
Teachers can build examinations manually by specifying questions, sub-questions (OR statements), keywords, and total marks. 
However, the system's biggest asset is its **Automated Extraction Engine**, which combines two distinct uploads to build a perfect digital rubric:
1. **Upload Original Question Paper:** The teacher uploads the blank question paper. Gemini 1.5 Flash extracts the exact structure, question text, and the *true maximum marks* per question. This ensures that scores are calculated against the true maximum (e.g., out of 20) rather than assuming a reference student's potentially flawed score (like a 17/20) is the absolute ceiling.
2. **Upload Reference Answer Paper:** This complements the question paper. By uploading a correctly answered paper (from a topper or answer key), the AI extracts the contextual answers and expected diagrams. It binds these model answers to the questions extracted previously.
3. **Database Insertion:** The system stores the combined data, seamlessly mapping the true physical constraints of the exam alongside expected keywords and reference answers without manual data entry.

### Phase 2: Grading Student Submissions (The Pipeline)
When a student's answer sheet is uploaded:
1. **Unstructured Parsing:** Gemini 1.5 Flash parses the student's submission. It is explicitly instructed to handle **random ordering** of questions dynamically, mapping answered text to the correct question ID regardless of page state.
2. **Vision Abstraction:** OpenCV applies a Gaussian Blur followed by Canny Edge contour detection `cv2.findContours` to hunt for diagram regions (any drawing covering >2% of the image).
3. **Dual Ensemble Scoring:** 
   - An ML pipeline calculates mathematical similarities.
   - A concurrent LLM pipeline generates qualitative feedback.
4. **Weighted Resolution:** The system outputs the final percentage based on a mathematical merge of the structural ML check (20%) and contextual AI check (80%), rounding up the closest marks.
5. **PDF Generation:** Using `reportlab`, ExamAI triggers an automated generation of an A4-styled Assessment Report PDF with a detailed ML-grade breakdown and textual narrative.

---

## 🧠 3. Machine Learning Models: The Ensemble Pipeline

ExamAI evaluates textual similarity utilizing 4 different Natural Language Processing models, 1 computer vision module, and 1 clustering algorithm. This prevents 'hallucinations' by anchoring the LLM evaluation to strict mathematical similarity checks.

### NLP Model 1: Sentence-BERT (`all-MiniLM-L6-v2`) — *40% ML Weight*
- **Mechanism:** Transforms the student's answer and the reference answer into 384-dimensional dense vectors using HuggingFace sentence-transformers.
- **Role:** Calculates the **Cosine Similarity** of the vectors. This measures *Semantic Meaning*. Even if a student uses different phrasing than the reference, SBERT understands the contextual equivalence.

### NLP Model 2: TF-IDF + Cosine Similarity — *25% ML Weight*
- **Mechanism:** `TfidfVectorizer` (from Sklearn) calculates the Term Frequency-Inverse Document Frequency of the text, followed by a raw cosine angle comparison.
- **Role:** Measures **Vocabulary Overlap**. It penalizes the answer if core technical terminology present in the reference is missing in the student's sheet.

### NLP Model 3: ROUGE-L (LCS-based) — *20% ML Weight*
- **Mechanism:** Implements a Longest Common Subsequence (LCS) matrix array across the text string. 
- **Role:** Measures **Sequence & Structure Matching**. Particularly useful for mathematical or step-by-step logic, where the order of words structurally matters.

### NLP Model 4: Keyword Coverage (BM25 Logic) — *15% ML Weight*
- **Mechanism:** A direct subset intersection that checks for the exact presence of predefined keywords in the user's string.
- **Role:** Ensures the baseline expected terms are hit.

### Computer Vision: OpenCV SSIM (Structural Similarity)
- **Mechanism:** Once diagram contours are isolated and resized to identical vectors, `skimage.metrics.structural_similarity` (SSIM) is run over the grayscale layouts.
- **Role:** Evaluates whether the geometry and layout of a student's drawn diagram structurally matches the teacher's reference diagram.

### Insight Generation: Sklearn KMeans Clustering
- **Mechanism:** Gathers TF-IDF arrays of all student answers per question and implements `KMeans(n_clusters=3)` on the array.
- **Role:** Groups student answers automatically based on textual similarity. If 15 students end up in the exact same cluster with incorrect answers, the teacher instantly discovers a **shared misconception** or heavy **plagiarising/copying**.

### LLM Pipeline: Google Gemini 1.5 Flash
- **Mechanism:** Utilizing Google's high-context foundational models.
- **Role:** Creates an exhaustive list of "Strengths" and "What to Improve" arrays for each question so that students understand *why* they lost marks. 

---

## 📊 4. How Models Power the Analytics Dashboard

The system doesn't only grade; it translates the ensemble output into visual intelligence via the Analytics Engine (located in `backend/routes/analytics_routes.py` and `backend/ml/charts.py`).

1. **ML Accuracy & MAE (Mean Absolute Error):** 
   - When a teacher reviews a paper, they can **Override** the ML-generated grade. 
   - The backend specifically computes the MAE and correlation coefficients pairing the AI's predicted score versus the Human's newly overridden score. The dashboard actively displays how close the ML is to mimicking the physical teacher.

2. **Question Performance Heatmap:** 
   - The database compiles a matrix of `Student Names` vs `Question Numbers`.
   - Dark Green represents perfect extraction and scoring, Red represents low scores. Teachers can quickly scan horizontally to see if a student failed, or scan vertically to see if the *entire class* failed a specific question (identifying a curriculum gap).

3. **Pass Rates & Class Curve (Histograms):**
   - Implements Matplotlib / Seaborn KDE (Kernel Density Estimation) to plot grade distribution, immediately indicating if an exam was too difficult for the batch.

4. **Student Radar Charts:**
   - In the student portal, individual grades over multiple exams are plotted onto Radar/Spider graphs to reflect long-term subject mastery.

---

## 📑 5. Auto-Generated PDF Architecture

After the ML pipeline concludes grading in `submission_routes.py`, the system bridges into `ml/report_gen.py`.
- Generates a styled A4 Assessment Report using **ReportLab**.
- Compiles the student's demographic details, Pass/Fail (threshold checks), Total calculated percentages, and the individual Breakdown Array of the ML tools.
- Embeds the specific textual narrative Feedback & Improvements array retrieved from Gemini right into the PDF for immediate parent/student dissemination.
