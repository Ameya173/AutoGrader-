const API = 'http://localhost:5000/api';

const Auth = {
  token: () => localStorage.getItem('examai_token'),
  user:  () => JSON.parse(localStorage.getItem('examai_user') || 'null'),
  set:   (t, u) => { localStorage.setItem('examai_token', t); localStorage.setItem('examai_user', JSON.stringify(u)); },
  clear: () => { localStorage.removeItem('examai_token'); localStorage.removeItem('examai_user'); },
  guard: (role) => {
    const u = Auth.user(), t = Auth.token();
    if (!u || !t) { console.log('AUTH GUARD: No user or token'); location.href = '../index.html'; return false; }
    const uRole = String(u.role || '').toLowerCase();
    const targetRole = String(role || '').toLowerCase();
    if (role && uRole !== targetRole) { 
      console.log(`AUTH GUARD: Role mismatch. User is '${uRole}', target is '${targetRole}'`);
      location.href = '../index.html'; 
      return false; 
    }
    return true;
  }
};

async function call(method, path, body, isForm) {
  const h = { Authorization: `Bearer ${Auth.token()}` };
  if (!isForm) h['Content-Type'] = 'application/json';
  const opts = { method, headers: h };
  if (body) opts.body = isForm ? body : JSON.stringify(body);
  const r = await fetch(`${API}${path}`, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || d.message || `HTTP ${r.status}`);
  return d;
}
const api = {
  get:    p      => call('GET', p),
  post:   (p, b) => call('POST', p, b),
  put:    (p, b) => call('PUT', p, b),
  patch:  (p, b) => call('PATCH', p, b),
  delete: p      => call('DELETE', p),
  upload: (p, f) => call('POST', p, f, true),
};

let _toastT;
function toast(msg, type='i') {
  let el = document.getElementById('_toast');
  if (!el) { el = document.createElement('div'); el.id = '_toast'; el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.className = `toast toast-${type} show`;
  clearTimeout(_toastT); _toastT = setTimeout(() => el.classList.remove('show'), 3200);
}

function openModal(id) { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }

function navTo(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + id)?.classList.add('active');
  document.getElementById('nav-' + id)?.classList.add('active');
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function fmtDate(iso) { if (!iso) return '—'; return new Date(iso).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}); }
function timeAgo(iso) {
  if (!iso) return '—';
  const d = (Date.now() - new Date(iso))/1000;
  if (d<60) return 'just now'; if (d<3600) return Math.floor(d/60)+'m ago';
  if (d<86400) return Math.floor(d/3600)+'h ago'; return Math.floor(d/86400)+'d ago';
}
function grade(pct) {
  if (pct>=90) return {g:'A+',c:'#059669'}; if (pct>=80) return {g:'A',c:'#059669'};
  if (pct>=70) return {g:'B',c:'#2563EB'}; if (pct>=60) return {g:'C',c:'#D97706'};
  if (pct>=50) return {g:'D',c:'#F97316'}; return {g:'F',c:'#DC2626'};
}
function progColor(pct) { if (pct>=70) return '#059669'; if (pct>=50) return '#D97706'; return '#DC2626'; }

function initSidebar() {
  const u = Auth.user(); if (!u) return;
  const av = document.getElementById('sb-av');
  if (av) {
    av.textContent = u.name.charAt(0).toUpperCase();
    av.style.background = u.role==='teacher'?'rgba(37,99,235,.2)':'rgba(5,150,105,.2)';
    av.style.color = u.role==='teacher'?'#2563EB':'#059669';
  }
  const n = document.getElementById('sb-name'); if (n) n.textContent = u.name;
  const r = document.getElementById('sb-role'); if (r) r.textContent = u.role.charAt(0).toUpperCase()+u.role.slice(1);
}

function logout() { Auth.clear(); location.href = '../index.html'; }

const SPIN = `<svg class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2.5" stroke-dasharray="55" stroke-dashoffset="18"/></svg>`;

function empty(icon, title, desc, action='') {
  return `<div style="text-align:center;padding:50px 20px">
    <div style="font-size:2.2rem;opacity:.25;margin-bottom:10px">${icon}</div>
    <div style="font-size:.86rem;font-weight:600;color:var(--text2);margin-bottom:4px">${title}</div>
    <div style="font-size:.75rem;color:var(--text3)">${desc}</div>
    ${action?`<div style="margin-top:14px">${action}</div>`:''}
  </div>`;
}

function aiLoad(msg) {
  return `<div class="ai-load">🤖 <span>${msg}</span><span class="dots"><span></span><span></span><span></span></span></div>`;
}

function toggleCard(head) {
  const body = head.nextElementSibling;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  const arr = head.querySelector('.arr');
  if (arr) arr.textContent = open ? '▼' : '▲';
}

window.addEventListener('click', e => { if (e.target.classList.contains('overlay')) e.target.classList.remove('open'); });
