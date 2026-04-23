import os, jwt, bcrypt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, g
from utils.local_db import get_user

SECRET = os.getenv('SECRET_KEY', 'examai2026secret')

def hash_pw(pw):   return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def check_pw(pw, h): return bcrypt.checkpw(pw.encode(), h.encode())

def make_token(uid, role):
    return jwt.encode({'sub': uid, 'role': role,
                       'exp': datetime.now(timezone.utc) + timedelta(days=30)},
                      SECRET, algorithm='HS256')

def decode_token(tok):
    return jwt.decode(tok, SECRET, algorithms=['HS256'])

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'No token'}), 401
        try:
            payload = decode_token(auth[7:])
            user = get_user(payload['sub'])
            if not user:
                print(f"AUTH ERROR: User {payload['sub']} not found in DB")
                return jsonify({'error': 'User not found'}), 401
            
            g.user = user
            g.uid = payload['sub']
            
            # Robust role detection
            db_role = str(user.get('role', '')).strip().lower()
            tok_role = str(payload.get('role', '')).strip().lower()
            g.role = db_role or tok_role
            
            print(f"AUTH SUCCESS: User={g.user.get('name')} Role={g.role}")

        except Exception as e:
            print(f"AUTH EXCEPTION: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return wrapper

def require_teacher(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        role = str(getattr(g, 'role', '')).strip().lower()
        if role != 'teacher': 
            print(f"FORBIDDEN: User {getattr(g, 'uid', 'unknown')} is {role}, but teacher required")
            return jsonify({'error': 'Teacher only'}), 403

        return f(*args, **kwargs)
    return wrapper

def require_student(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if str(getattr(g, 'role', '')).lower() != 'student': 
            return jsonify({'error': 'Student only'}), 403

        return f(*args, **kwargs)
    return wrapper
