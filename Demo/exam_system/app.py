"""
在线考试系统 - Online Exam System
基于 Flask + SQLite 构建
"""

import os
import sys
import json
import random
import sqlite3
import hashlib
import secrets
import threading
import webbrowser
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g)

# ── 路径兼容（PyInstaller 打包后） ──────────────────────────────────────
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, 'frozen', False) else __file__
)), 'exam_system.db')

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=2)

# ── 数据库 ──────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role     TEXT NOT NULL DEFAULT 'student',  -- admin / student
        name     TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS exams (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT,
        duration    INTEGER DEFAULT 60,   -- minutes
        pass_score  INTEGER DEFAULT 60,
        shuffle     INTEGER DEFAULT 1,    -- shuffle questions
        status      TEXT DEFAULT 'draft', -- draft/published/closed
        created_by  INTEGER,
        created_at  TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS questions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id     INTEGER NOT NULL,
        qtype       TEXT NOT NULL,        -- single/multi/truefalse/fillblank
        content     TEXT NOT NULL,
        options     TEXT,                 -- JSON array
        answer      TEXT NOT NULL,
        explanation TEXT,
        score       INTEGER DEFAULT 5,
        sort_order  INTEGER DEFAULT 0,
        FOREIGN KEY(exam_id) REFERENCES exams(id)
    );
    CREATE TABLE IF NOT EXISTS exam_records (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id    INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        answers    TEXT,                  -- JSON
        score      INTEGER DEFAULT 0,
        total      INTEGER DEFAULT 0,
        passed     INTEGER DEFAULT 0,
        started_at TEXT DEFAULT (datetime('now','localtime')),
        finished_at TEXT,
        time_used  INTEGER DEFAULT 0,     -- seconds
        FOREIGN KEY(exam_id) REFERENCES exams(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    # 默认管理员
    pw = hashlib.sha256('admin123'.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO users(username,password,role,name) VALUES(?,?,?,?)",
               ('admin', pw, 'admin', '系统管理员'))
    # 默认学生
    pw2 = hashlib.sha256('student123'.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO users(username,password,role,name) VALUES(?,?,?,?)",
               ('student', pw2, 'student', '测试学生'))
    db.commit()
    _seed_demo_exam(db)
    db.close()

def _seed_demo_exam(db):
    """插入示例考试（仅首次）"""
    if db.execute("SELECT COUNT(*) FROM exams").fetchone()[0] > 0:
        return
    admin_id = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    db.execute("""INSERT INTO exams(title,description,duration,pass_score,shuffle,status,created_by)
                  VALUES(?,?,?,?,?,?,?)""",
               ('Python 基础知识测验', '测试 Python 基础知识，共 5 道题', 30, 60, 1, 'published', admin_id))
    eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    qs = [
        ('single', 'Python 中哪个关键字用于定义函数？',
         json.dumps(['class','def','func','define']), 'B',
         'def 关键字用于定义函数', 20),
        ('single', '以下哪个是 Python 的不可变数据类型？',
         json.dumps(['列表 list','字典 dict','集合 set','元组 tuple']), 'D',
         'tuple 是不可变序列', 20),
        ('multi', '以下哪些是 Python 内置函数？（多选）',
         json.dumps(['print()','len()','push()','range()']), 'A,B,D',
         'push() 不是内置函数', 20),
        ('truefalse', 'Python 是一种编译型语言。',
         json.dumps(['正确','错误']), 'B',
         'Python 是解释型语言', 20),
        ('fillblank', 'Python 中获取列表长度的内置函数是 ___。',
         None, 'len',
         '使用 len() 函数', 20),
    ]
    for i, (qt, content, opts, ans, exp, sc) in enumerate(qs):
        db.execute("""INSERT INTO questions(exam_id,qtype,content,options,answer,explanation,score,sort_order)
                      VALUES(?,?,?,?,?,?,?,?)""",
                   (eid, qt, content, opts, ans, exp, sc, i))
    db.commit()

# ── 认证装饰器 ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('权限不足', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return login_required(decorated)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

# ══════════════════════════════════════════════════════════════════════════
#  路由
# ══════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('student_dashboard'))

# ── 登录 / 注销 ──────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        row = get_db().execute(
            "SELECT * FROM users WHERE username=? AND password=?", (u, hash_pw(p))
        ).fetchone()
        if row:
            session.permanent = True
            session['user_id'] = row['id']
            session['username'] = row['username']
            session['name']     = row['name'] or row['username']
            session['role']     = row['role']
            return redirect(url_for('index'))
        flash('用户名或密码错误', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        n = request.form['name'].strip()
        if not u or not p:
            flash('用户名和密码不能为空', 'danger')
        else:
            try:
                get_db().execute(
                    "INSERT INTO users(username,password,role,name) VALUES(?,?,?,?)",
                    (u, hash_pw(p), 'student', n)
                )
                get_db().commit()
                flash('注册成功，请登录', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('用户名已存在', 'danger')
    return render_template('register.html')

# ── 学生端 ───────────────────────────────────────────────────────────────
@app.route('/student')
@login_required
def student_dashboard():
    db = get_db()
    exams = db.execute(
        "SELECT * FROM exams WHERE status='published' ORDER BY created_at DESC"
    ).fetchall()
    records = {r['exam_id']: r for r in db.execute(
        "SELECT * FROM exam_records WHERE user_id=? ORDER BY started_at DESC",
        (session['user_id'],)
    ).fetchall()}
    return render_template('student_dashboard.html', exams=exams, records=records)

@app.route('/exam/<int:exam_id>/start')
@login_required
def start_exam(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=? AND status='published'", (exam_id,)).fetchone()
    if not exam:
        flash('考试不存在或未开放', 'warning')
        return redirect(url_for('student_dashboard'))
    # 检查是否已有未完成记录
    rec = db.execute(
        "SELECT * FROM exam_records WHERE exam_id=? AND user_id=? AND finished_at IS NULL",
        (exam_id, session['user_id'])
    ).fetchone()
    if not rec:
        db.execute(
            "INSERT INTO exam_records(exam_id,user_id) VALUES(?,?)",
            (exam_id, session['user_id'])
        )
        db.commit()
        rec = db.execute(
            "SELECT * FROM exam_records WHERE exam_id=? AND user_id=? AND finished_at IS NULL",
            (exam_id, session['user_id'])
        ).fetchone()
    qs = db.execute(
        "SELECT * FROM questions WHERE exam_id=? ORDER BY sort_order", (exam_id,)
    ).fetchall()
    qs_list = [dict(q) for q in qs]
    for q in qs_list:
        if q['options']:
            q['options'] = json.loads(q['options'])
    if exam['shuffle']:
        random.shuffle(qs_list)
    return render_template('exam_take.html', exam=exam, questions=qs_list, record=rec)

@app.route('/exam/<int:record_id>/submit', methods=['POST'])
@login_required
def submit_exam(record_id):
    db = get_db()
    rec = db.execute(
        "SELECT * FROM exam_records WHERE id=? AND user_id=? AND finished_at IS NULL",
        (record_id, session['user_id'])
    ).fetchone()
    if not rec:
        flash('提交失败', 'danger')
        return redirect(url_for('student_dashboard'))

    answers = {}
    for k, v in request.form.items():
        if k.startswith('q_'):
            qid = k[2:]
            if isinstance(v, list):
                answers[qid] = ','.join(sorted(v))
            else:
                answers[qid] = v.strip()
    # multi checkbox
    for k in request.form.keys():
        if k.startswith('m_'):
            qid = k[2:]
            vals = request.form.getlist(k)
            answers[qid] = ','.join(sorted(vals))

    qs = db.execute(
        "SELECT * FROM questions WHERE exam_id=?", (rec['exam_id'],)
    ).fetchall()
    total = sum(q['score'] for q in qs)
    score = 0
    detail = {}
    for q in qs:
        qid = str(q['id'])
        user_ans = answers.get(qid, '').strip().upper()
        correct   = q['answer'].strip().upper()
        is_correct = False
        if q['qtype'] == 'fillblank':
            is_correct = user_ans.lower() == correct.lower()
        else:
            is_correct = user_ans == correct
        if is_correct:
            score += q['score']
        detail[qid] = {'user': answers.get(qid,''), 'correct': q['answer'],
                       'ok': is_correct, 'score': q['score'], 'type': q['qtype']}

    exam = db.execute("SELECT * FROM exams WHERE id=?", (rec['exam_id'],)).fetchone()
    passed = 1 if total > 0 and (score / total * 100) >= exam['pass_score'] else 0
    time_used = int((datetime.now() - datetime.strptime(
        rec['started_at'], '%Y-%m-%d %H:%M:%S')).total_seconds())

    db.execute("""UPDATE exam_records SET answers=?,score=?,total=?,passed=?,
                  finished_at=datetime('now','localtime'),time_used=? WHERE id=?""",
               (json.dumps(detail), score, total, passed, time_used, record_id))
    db.commit()
    return redirect(url_for('exam_result', record_id=record_id))

@app.route('/result/<int:record_id>')
@login_required
def exam_result(record_id):
    db = get_db()
    rec = db.execute(
        "SELECT er.*, e.title, e.pass_score, e.duration FROM exam_records er "
        "JOIN exams e ON er.exam_id=e.id WHERE er.id=? AND er.user_id=?",
        (record_id, session['user_id'])
    ).fetchone()
    if not rec:
        flash('记录不存在', 'warning')
        return redirect(url_for('student_dashboard'))
    qs = db.execute(
        "SELECT * FROM questions WHERE exam_id=? ORDER BY sort_order", (rec['exam_id'],)
    ).fetchall()
    answers = json.loads(rec['answers'] or '{}')
    qs_list = [dict(q) for q in qs]
    for q in qs_list:
        if q['options']:
            q['options'] = json.loads(q['options'])
    return render_template('exam_result.html', rec=rec, questions=qs_list, answers=answers)

# ── 管理端 ───────────────────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'exams':    db.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
        'users':    db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        'records':  db.execute("SELECT COUNT(*) FROM exam_records WHERE finished_at IS NOT NULL").fetchone()[0],
        'pass_rate': 0,
    }
    total_r = db.execute("SELECT COUNT(*) FROM exam_records WHERE finished_at IS NOT NULL").fetchone()[0]
    pass_r  = db.execute("SELECT COUNT(*) FROM exam_records WHERE passed=1").fetchone()[0]
    if total_r: stats['pass_rate'] = round(pass_r / total_r * 100, 1)
    recent = db.execute(
        "SELECT er.*, u.name as uname, e.title as etitle FROM exam_records er "
        "JOIN users u ON er.user_id=u.id JOIN exams e ON er.exam_id=e.id "
        "WHERE er.finished_at IS NOT NULL ORDER BY er.finished_at DESC LIMIT 10"
    ).fetchall()
    return render_template('admin_dashboard.html', stats=stats, recent=recent)

# 考试列表
@app.route('/admin/exams')
@admin_required
def admin_exams():
    exams = get_db().execute(
        "SELECT e.*, COUNT(q.id) as qcount, u.name as creator FROM exams e "
        "LEFT JOIN questions q ON e.id=q.exam_id "
        "LEFT JOIN users u ON e.created_by=u.id "
        "GROUP BY e.id ORDER BY e.created_at DESC"
    ).fetchall()
    return render_template('admin_exams.html', exams=exams)

# 创建/编辑考试
@app.route('/admin/exam/new', methods=['GET','POST'])
@app.route('/admin/exam/<int:exam_id>/edit', methods=['GET','POST'])
@admin_required
def admin_exam_edit(exam_id=None):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone() if exam_id else None
    if request.method == 'POST':
        title = request.form['title'].strip()
        desc  = request.form['description'].strip()
        dur   = int(request.form.get('duration', 60))
        ps    = int(request.form.get('pass_score', 60))
        sh    = 1 if request.form.get('shuffle') else 0
        if exam_id:
            db.execute("UPDATE exams SET title=?,description=?,duration=?,pass_score=?,shuffle=? WHERE id=?",
                       (title, desc, dur, ps, sh, exam_id))
        else:
            db.execute("INSERT INTO exams(title,description,duration,pass_score,shuffle,created_by) VALUES(?,?,?,?,?,?)",
                       (title, desc, dur, ps, sh, session['user_id']))
            exam_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()
        flash('保存成功', 'success')
        return redirect(url_for('admin_exam_questions', exam_id=exam_id))
    return render_template('admin_exam_edit.html', exam=exam)

# 题目管理
@app.route('/admin/exam/<int:exam_id>/questions')
@admin_required
def admin_exam_questions(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    qs   = db.execute("SELECT * FROM questions WHERE exam_id=? ORDER BY sort_order", (exam_id,)).fetchall()
    qs_list = [dict(q) for q in qs]
    for q in qs_list:
        if q['options']:
            q['options'] = json.loads(q['options'])
    total_score = sum(q['score'] for q in qs_list)
    return render_template('admin_questions.html', exam=exam, questions=qs_list, total_score=total_score)

# 添加/编辑题目
@app.route('/admin/exam/<int:exam_id>/question/new', methods=['GET','POST'])
@app.route('/admin/exam/<int:exam_id>/question/<int:qid>/edit', methods=['GET','POST'])
@admin_required
def admin_question_edit(exam_id, qid=None):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    q = db.execute("SELECT * FROM questions WHERE id=? AND exam_id=?", (qid, exam_id)).fetchone() if qid else None
    if q:
        q = dict(q)
        if q['options']: q['options'] = json.loads(q['options'])
    if request.method == 'POST':
        qtype   = request.form['qtype']
        content = request.form['content'].strip()
        answer  = request.form['answer'].strip()
        exp     = request.form.get('explanation','').strip()
        sc      = int(request.form.get('score', 5))
        opts = None
        if qtype in ('single','multi','truefalse'):
            raw = [request.form.get(f'opt_{c}','').strip() for c in 'ABCD']
            opts = json.dumps([o for o in raw if o])
        if qid:
            db.execute(
                "UPDATE questions SET qtype=?,content=?,options=?,answer=?,explanation=?,score=? WHERE id=?",
                (qtype, content, opts, answer, exp, sc, qid)
            )
        else:
            max_order = db.execute("SELECT MAX(sort_order) FROM questions WHERE exam_id=?", (exam_id,)).fetchone()[0] or 0
            db.execute(
                "INSERT INTO questions(exam_id,qtype,content,options,answer,explanation,score,sort_order) VALUES(?,?,?,?,?,?,?,?)",
                (exam_id, qtype, content, opts, answer, exp, sc, max_order+1)
            )
        db.commit()
        flash('题目已保存', 'success')
        return redirect(url_for('admin_exam_questions', exam_id=exam_id))
    return render_template('admin_question_edit.html', exam=exam, q=q)

# 删除题目
@app.route('/admin/question/<int:qid>/delete', methods=['POST'])
@admin_required
def admin_question_delete(qid):
    db = get_db()
    q = db.execute("SELECT exam_id FROM questions WHERE id=?", (qid,)).fetchone()
    if q:
        db.execute("DELETE FROM questions WHERE id=?", (qid,))
        db.commit()
        flash('题目已删除', 'success')
        return redirect(url_for('admin_exam_questions', exam_id=q['exam_id']))
    return redirect(url_for('admin_exams'))

# 发布/关闭考试
@app.route('/admin/exam/<int:exam_id>/status/<action>', methods=['POST'])
@admin_required
def admin_exam_status(exam_id, action):
    status_map = {'publish':'published','close':'closed','draft':'draft'}
    s = status_map.get(action)
    if s:
        get_db().execute("UPDATE exams SET status=? WHERE id=?", (s, exam_id))
        get_db().commit()
        flash(f'状态已更新为 {s}', 'success')
    return redirect(url_for('admin_exams'))

# 删除考试
@app.route('/admin/exam/<int:exam_id>/delete', methods=['POST'])
@admin_required
def admin_exam_delete(exam_id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE exam_id=?", (exam_id,))
    db.execute("DELETE FROM exam_records WHERE exam_id=?", (exam_id,))
    db.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    db.commit()
    flash('考试已删除', 'success')
    return redirect(url_for('admin_exams'))

# 成绩查看
@app.route('/admin/records')
@admin_required
def admin_records():
    db = get_db()
    exam_id = request.args.get('exam_id', type=int)
    query = ("SELECT er.*, u.name as uname, u.username, e.title as etitle, e.pass_score "
             "FROM exam_records er JOIN users u ON er.user_id=u.id "
             "JOIN exams e ON er.exam_id=e.id WHERE er.finished_at IS NOT NULL ")
    params = []
    if exam_id:
        query += "AND er.exam_id=? "
        params.append(exam_id)
    query += "ORDER BY er.finished_at DESC"
    records = db.execute(query, params).fetchall()
    exams   = db.execute("SELECT id,title FROM exams ORDER BY title").fetchall()
    return render_template('admin_records.html', records=records, exams=exams, selected_exam=exam_id)

# 用户管理
@app.route('/admin/users')
@admin_required
def admin_users():
    users = get_db().execute(
        "SELECT u.*, COUNT(er.id) as exam_count FROM users u "
        "LEFT JOIN exam_records er ON u.id=er.user_id GROUP BY u.id ORDER BY u.created_at DESC"
    ).fetchall()
    return render_template('admin_users.html', users=users)

@app.route('/admin/user/<int:uid>/delete', methods=['POST'])
@admin_required
def admin_user_delete(uid):
    if uid == session['user_id']:
        flash('不能删除自己', 'danger')
    else:
        db = get_db()
        db.execute("DELETE FROM exam_records WHERE user_id=?", (uid,))
        db.execute("DELETE FROM users WHERE id=?", (uid,))
        db.commit()
        flash('用户已删除', 'success')
    return redirect(url_for('admin_users'))

# 重置密码
@app.route('/admin/user/<int:uid>/reset_pw', methods=['POST'])
@admin_required
def admin_reset_pw(uid):
    new_pw = request.form.get('new_pw','123456').strip() or '123456'
    get_db().execute("UPDATE users SET password=? WHERE id=?", (hash_pw(new_pw), uid))
    get_db().commit()
    flash(f'密码已重置为: {new_pw}', 'success')
    return redirect(url_for('admin_users'))

# API: 答题记录详情
@app.route('/api/record/<int:record_id>')
@login_required
def api_record(record_id):
    db = get_db()
    rec = db.execute("SELECT * FROM exam_records WHERE id=?", (record_id,)).fetchone()
    if not rec: return jsonify({'error': 'not found'}), 404
    if session['role'] != 'admin' and rec['user_id'] != session['user_id']:
        return jsonify({'error': 'forbidden'}), 403
    return jsonify(dict(rec))

# ══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    port = 5000
    print(f"\n{'='*50}")
    print(f"  在线考试系统已启动")
    print(f"  访问地址: http://127.0.0.1:{port}")
    print(f"  管理员账号: admin / admin123")
    print(f"  学生账号:   student / student123")
    print(f"{'='*50}\n")
    # 延迟打开浏览器
    threading.Timer(1.0, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    app.run(host='0.0.0.0', port=port, debug=False)
