"""Auth Routes"""
from flask import Blueprint, request, jsonify, g
from utils.local_db import create_user, get_user_by_email, get_user
from utils.auth import hash_pw, check_pw, make_token, require_auth

auth_bp = Blueprint('auth', __name__)

DEMO = {
    'teacher@demo.com': {'name':'Dr. Demo Teacher','role':'teacher','subject':'Computer Science'},
    'student@demo.com': {'name':'Demo Student','role':'student','subject':'B.Tech CSE'}
}

@auth_bp.route('/register', methods=['POST'])
def register():
    d = request.json or {}
    name,email,pw,role = d.get('name','').strip(), d.get('email','').strip().lower(), d.get('password',''), d.get('role','student')
    if not all([name,email,pw]): return jsonify({'error':'All fields required'}),400
    if role not in ('teacher','student'): return jsonify({'error':'Invalid role'}),400
    user, err = create_user(name, email, hash_pw(pw), role, d.get('subject',''))
    if err: return jsonify({'error': err}),409
    token = make_token(user['id'], role)
    u = {k:v for k,v in user.items() if k!='password'}
    return jsonify({'user':u,'token':token}),201

@auth_bp.route('/login', methods=['POST'])
def login():
    d = request.json or {}
    email,pw = d.get('email','').strip().lower(), d.get('password','')
    # Demo accounts
    if email in DEMO:
        from utils.local_db import get_user_by_email as gube, create_user
        user = gube(email)
        if not user:
            user, _ = create_user(DEMO[email]['name'], email, hash_pw('demo123'), DEMO[email]['role'], DEMO[email].get('subject',''))
        token = make_token(user['id'], user['role'])
        return jsonify({'user':{k:v for k,v in user.items() if k!='password'},'token':token})
    user = get_user_by_email(email)
    if not user: return jsonify({'error':'Email not found'}),401
    if not check_pw(pw, user['password']): return jsonify({'error':'Wrong password'}),401
    token = make_token(user['id'], user['role'])
    return jsonify({'user':{k:v for k,v in user.items() if k!='password'},'token':token})

@auth_bp.route('/me', methods=['GET'])
@require_auth
def me():
    return jsonify({k:v for k,v in g.user.items() if k!='password'})

@auth_bp.route('/students', methods=['GET'])
@require_auth
def list_students():
    if g.role != 'teacher': return jsonify({'error': 'Teacher only'}), 403
    from utils.local_db import get_students
    return jsonify([{k:v for k,v in s.items() if k!='password'} for s in get_students()])
