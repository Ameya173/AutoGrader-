"""
local_db.py — JSON file-based database
No MongoDB, no Firebase. Just flat JSON files.
"""
import json, os, uuid
from datetime import datetime, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(DB_DIR, exist_ok=True)

def _path(name):
    return os.path.join(DB_DIR, f'{name}.json')

def _load(name):
    p = _path(name)
    if not os.path.exists(p):
        return {}
    with open(p, 'r') as f:
        return json.load(f)

def _save(name, data):
    with open(_path(name), 'w') as f:
        json.dump(data, f, indent=2, default=str)

def now():
    return datetime.now(timezone.utc).isoformat()

def new_id():
    return str(uuid.uuid4())[:8]

# ── USERS ──
def get_users():          return _load('users')
def save_users(d):        _save('users', d)

def create_user(name, email, password_hash, role, subject=''):
    users = get_users()
    if any(u['email'] == email for u in users.values()):
        return None, 'Email already registered'
    uid = new_id()
    users[uid] = {'id': uid, 'name': name, 'email': email,
                  'password': password_hash, 'role': role,
                  'subject': subject, 'createdAt': now()}
    save_users(users)
    return users[uid], None

def get_user_by_email(email):
    return next((u for u in get_users().values() if u['email'] == email), None)

def get_user(uid):
    return get_users().get(uid)

def get_students():
    return [u for u in get_users().values() if u.get('role') == 'student']

# ── EXAMS ──
def get_exams():          return _load('exams')
def save_exams(d):        _save('exams', d)

def create_exam(data):
    exams = get_exams()
    eid = new_id()
    data['id'] = eid
    data['createdAt'] = now()
    data.setdefault('status', 'draft')
    exams[eid] = data
    save_exams(exams)
    return data

def get_exam(eid):
    return get_exams().get(eid)

def update_exam(eid, updates):
    exams = get_exams()
    if eid not in exams:
        return None
    exams[eid].update(updates)
    exams[eid]['updatedAt'] = now()
    save_exams(exams)
    return exams[eid]

def delete_exam(eid):
    exams = get_exams()
    exams.pop(eid, None)
    save_exams(exams)

def get_teacher_exams(teacher_id):
    return [e for e in get_exams().values() if e.get('teacherId') == teacher_id]

def get_published_exams():
    return [e for e in get_exams().values() if e.get('status') == 'published']

# ── SUBMISSIONS ──
def get_submissions():    return _load('submissions')
def save_submissions(d):  _save('submissions', d)

def create_submission(data):
    subs = get_submissions()
    sid = new_id()
    data['id'] = sid
    data['createdAt'] = now()
    data.setdefault('status', 'pending')
    subs[sid] = data
    save_submissions(subs)
    return data

def get_submission(sid):
    return get_submissions().get(sid)

def update_submission(sid, updates):
    subs = get_submissions()
    if sid not in subs:
        return None
    subs[sid].update(updates)
    save_submissions(subs)
    return subs[sid]

def get_exam_submissions(exam_id):
    return [s for s in get_submissions().values() if s.get('examId') == exam_id]

def get_student_submissions(student_id):
    return [s for s in get_submissions().values() if s.get('studentId') == student_id]

def delete_submission(sid):
    subs = get_submissions()
    subs.pop(sid, None)
    save_submissions(subs)
