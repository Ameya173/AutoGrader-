"""ExamAI — Flask Backend"""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY','examai2026')
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB

CORS(app, resources={r"/api/*": {
    "origins": "*",
    "methods": ["GET","POST","PUT","DELETE","PATCH","OPTIONS"],
    "allow_headers": ["Content-Type","Authorization"]
}})

# ── Ensure dirs ──
for d in ['uploads/reference','uploads/submissions','uploads/reports','data']:
    os.makedirs(os.path.join(os.path.dirname(__file__), d), exist_ok=True)

# ── Register blueprints ──
from routes.auth_routes import auth_bp
from routes.exam_routes import exam_bp
from routes.submission_routes import sub_bp
from routes.analytics_routes import analytics_bp

app.register_blueprint(auth_bp,       url_prefix='/api/auth')
app.register_blueprint(exam_bp,       url_prefix='/api/exams')
app.register_blueprint(sub_bp,        url_prefix='/api/submissions')
app.register_blueprint(analytics_bp,  url_prefix='/api/analytics')

@app.route('/api/health')
def health():
    return jsonify({'status':'ok','version':'2.0',
                    'gemini': bool(os.getenv('GEMINI_API_KEY')),
                    'models': ['Sentence-BERT','TF-IDF','ROUGE-L','Keyword Coverage','OpenCV-SSIM','KMeans']})

@app.errorhandler(413)
def too_large(e): return jsonify({'error':'File too large (max 30MB)'}), 413

if __name__ == '__main__':
    port = int(os.getenv('PORT',5000))
    print(f"\n🚀 ExamAI Backend → http://localhost:{port}")
    print(f"   Gemini: {'✓' if os.getenv('GEMINI_API_KEY') else '✗ Missing GEMINI_API_KEY'}")
    print(f"   ML Models: SBERT · TF-IDF · ROUGE-L · Keywords · OpenCV · KMeans\n")
    app.run(host='0.0.0.0', port=port, debug=True)
