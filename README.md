# 🎓 AutoGrader (ExamAI) — Advanced AI Evaluation Suite

**AutoGrader** is a high-performance, production-ready AI evaluation system designed to automate the grading of unstructured student answer sheets. By combining a **Mathematical Ensemble ML Architecture** with **Google Gemini 1.5 Flash**, the system provides objective, consistent, and feedback-rich grading for handwritten text and diagrams.

---

## 🚀 1. Setup & Quick Start

The project utilizes a Python Flask REST API backend and a modern Vanilla JS/HTML/CSS frontend.

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

## 🏛 2. Core Architecture: The "Smart-Teacher" Workflow

AutoGrader supports three distinct setup options for exam creation, ensuring flexibility for various academic requirements.

### Phase 1: Context-Aware Exam Creation
1. **Option A: Reference Paper Upload**: Upload a perfectly marked topper's sheet. The AI extracts questions and uses them as the "Standard Answer Book."
2. **Option B: Study Material Enrichment**: Upload course PPTs or PDFs. The AI uses these as the primary source of truth, ensuring that model answers match specific classroom curriculum.
3. **Option C: AI Answer Key Generation (New!)**: 
   - **Zero-Manual Entry**: After adding questions (or extracting them from a blank paper), teachers can trigger the AI to automatically generate model answers and detailed rubrics.
   - **Mode: Search AI Knowledge**: Generates answers from general academic training data.
   - **Mode: Material Extraction**: Generates answers strictly grounded in the uploaded course materials.

### Phase 2: Grading Student Submissions (The Pipeline)
When a student's answer sheet is uploaded:
1. **Unstructured Parsing**: Handles random question ordering dynamically.
2. **Vision Extraction**: OpenCV hunts for diagram regions using `cv2.findContours`.
3. **Ensemble Logic**: Text is evaluated using 4 NLP models (40% SBERT, 25% TF-IDF, 20% ROUGE-L, 15% Keywords).
4. **Grading & Feedback**: Results are generated as an A4 Assessment Report PDF with subject-specific narrative feedback.

---

## 🔬 3. Verification & Transparency Tools

Designed for educators who require absolute accuracy, AutoGrader includes tools for manual cross-checking.

- **AI Research Logs**: For every generated answer, the AI provides a "Research Context" block. Teachers can click **"View AI Research Details"** to see exactly which snippet of material or concept was used for grading.
- **Strict Marks Enforcement**: The system strictly respects teacher-assigned marks. Rubric weights for detailed assessment parameters are automatically calculated to sum exactly to the teacher's specified total, ensuring mathematical consistency.

---

## 🧠 4. Machine Learning Models: The Ensemble Pipeline

To prevent "AI Hallucinations," the system anchors qualitatively generated grades to strict mathematical similarity checks across six different algorithms.

#### 1. Sentence-BERT (`all-MiniLM-L6-v2`) — *Semantic Meaning*
Transforms text into 384-dimensional dense vectors to calculate **Cosine Similarity**. Understands contextual equivalence even with different phrasing.

#### 2. TF-IDF + Cosine Similarity — *Vocabulary Check*
Measures technical terminology overlap. Penalizes answers that skip mandatory subject-specific keywords found in the reference.

#### 3. ROUGE-L (LCS-based) — *Structural Matching*
Implements a Longest Common Subsequence matrix. Ensures that step-by-step logic and sequence in technical definitions are correct.

#### 4. Keyword Coverage (BM25 Logic) — *Essential Terminology*
Direct subset intersection for predefined "Must-Have" keywords.

#### 5. OpenCV SSIM (Structural Similarity) — *Diagram Eval*
Grayscale layout comparison to evaluate handwritten diagrams against the teacher's reference.

#### 6. Sklearn KMeans Clustering — *Plagiarism & Insight*
Groups student answers automatically. Helps teachers identify shared misconceptions or copying patterns across the entire batch.

---

## 📊 5. Predictive Analytics & Insights

The system translates grading data into visual intelligence for institutional use:
- **ML Accuracy (MAE)**: Actively tracks the "Mean Absolute Error" between AI grades and Teacher overrides to measure system reliability.
- **Question Heatmap**: Identifies specific topics where the entire class struggled.
- **Pass/Fail Distribution**: Histograms and KDE plots showing the batch performance curve.

---

## 📑 6. Technical Stack
- **Backend**: Flask, JWT Auth, Google Generative AI (Gemini), Sklearn, LabReport (PDF).
- **Frontend**: Vanilla JS (ES6+), HTML5 Semantic Shell, CSS3 (Modular CSS).
- **Computer Vision**: OpenCV (cv2), SSIM.
- **Deployment**: Progressively Web App (PWA) compatible.
