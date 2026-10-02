import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'veli')
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASS', 'veli123'))
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'books.db')

RANKS = [
    (0, 'Acemi Okuyucu', 'bg-slate-100 text-slate-700 border-slate-300', 'fa-user-ninja'),
    (5, 'Onbaşı', 'bg-blue-100 text-blue-800 border-blue-300', 'fa-award'),
    (10, 'Çavuş', 'bg-emerald-100 text-emerald-800 border-emerald-300', 'fa-certificate'),
    (15, 'Teğmen', 'bg-purple-100 text-purple-800 border-purple-300', 'fa-star'),
    (20, 'Yüzbaşı', 'bg-amber-100 text-amber-800 border-amber-300', 'fa-medal'),
    (25, 'Binbaşı', 'bg-orange-100 text-orange-800 border-orange-300', 'fa-crown'),
    (30, 'Albay', 'bg-rose-100 text-rose-800 border-rose-300', 'fa-trophy'),
]

def get_rank(count):
    current = RANKS[0]
    next_count = RANKS[1][0]
    for i, rank in enumerate(RANKS):
        if count >= rank[0]:
            current = rank
            next_count = RANKS[i + 1][0] if i + 1 < len(RANKS) else None
    previous = current[0]
    if next_count:
        progress = int(((count - previous) / (next_count - previous)) * 100)
    else:
        progress = 100
    return {'title': current[1], 'badge_style': current[2], 'icon': current[3],
            'next_count': next_count, 'progress': min(100, max(0, progress))}

def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        page_count INTEGER NOT NULL,
        issue_date TEXT NOT NULL,
        return_date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')
    # Migrate old books table if it still uses student_name.
    cols = [r['name'] for r in conn.execute('PRAGMA table_info(books)').fetchall()]
    if 'student_name' in cols and 'student_id' not in cols:
        conn.execute('ALTER TABLE books RENAME TO books_old')
        conn.execute('''CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )''')
        old = conn.execute('SELECT * FROM books_old ORDER BY id').fetchall()
        for b in old:
            name = b['student_name'].strip()
            conn.execute('INSERT OR IGNORE INTO students(name) VALUES (?)', (name,))
            sid = conn.execute('SELECT id FROM students WHERE name=?', (name,)).fetchone()['id']
            conn.execute('''INSERT INTO books(id, student_id, title, author, page_count, issue_date, return_date, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (b['id'], sid, b['title'], b['author'], b['page_count'], b['issue_date'], b['return_date'], b['created_at']))
        conn.execute('DROP TABLE books_old')
    conn.commit(); conn.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    conn = db()
    rows = conn.execute('''SELECT s.id, s.name, COUNT(b.id) book_count,
                           COALESCE(SUM(b.page_count),0) total_pages
                           FROM students s LEFT JOIN books b ON b.student_id=s.id
                           GROUP BY s.id ORDER BY book_count DESC, s.name COLLATE NOCASE''').fetchall()
    total_books = conn.execute('SELECT COUNT(*) c FROM books').fetchone()['c']
    total_pages = conn.execute('SELECT COALESCE(SUM(page_count),0) p FROM books').fetchone()['p']
    students=[]
    for r in rows:
        x=dict(r); x['rank']=get_rank(x['book_count']); students.append(x)
    conn.close()
    return render_template('index.html', students=students, total_class_books=total_books, total_class_pages=total_pages)

@app.route('/student/<int:student_id>')
def student_detail(student_id):
    conn=db()
    student=conn.execute('SELECT * FROM students WHERE id=?',(student_id,)).fetchone()
    if not student:
        conn.close(); return ('Öğrenci bulunamadı',404)
    books=conn.execute('SELECT * FROM books WHERE student_id=? ORDER BY issue_date DESC,id DESC',(student_id,)).fetchall()
    rank=get_rank(len(books)); pages=sum(b['page_count'] for b in books)
    conn.close()
    return render_template('student.html', student=student, books=books, rank=rank, total_pages=pages)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        if request.form.get('username')==ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, request.form.get('password','')):
            session['is_admin']=True; session['username']=ADMIN_USERNAME
            return redirect(url_for('admin'))
        flash('Hatalı kullanıcı adı veya şifre!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    conn=db()
    students=conn.execute('''SELECT s.id,s.name,COUNT(b.id) book_count,COALESCE(SUM(b.page_count),0) total_pages
                             FROM students s LEFT JOIN books b ON b.student_id=s.id
                             GROUP BY s.id ORDER BY s.name COLLATE NOCASE''').fetchall()
    books=conn.execute('''SELECT b.*,s.name student_name FROM books b JOIN students s ON s.id=b.student_id
                          ORDER BY b.id DESC''').fetchall()
    conn.close(); return render_template('admin.html',students=students,books=books)

@app.route('/admin/student/add',methods=['POST'])
@login_required
def add_student():
    name=request.form.get('name','').strip()
    if not name: flash('Öğrenci adı boş olamaz.','error')
    else:
        conn=db()
        try: conn.execute('INSERT INTO students(name) VALUES (?)',(name.title(),)); conn.commit(); flash('Öğrenci eklendi.','success')
        except sqlite3.IntegrityError: flash('Bu öğrenci zaten kayıtlı.','error')
        finally: conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/student/edit/<int:id>',methods=['POST'])
@login_required
def edit_student(id):
    name=request.form.get('name','').strip()
    conn=db(); conn.execute('UPDATE students SET name=? WHERE id=?',(name.title(),id)); conn.commit(); conn.close()
    flash('Öğrenci güncellendi.','success'); return redirect(url_for('admin'))

@app.route('/admin/student/delete/<int:id>',methods=['POST'])
@login_required
def delete_student(id):
    conn=db(); conn.execute('DELETE FROM books WHERE student_id=?',(id,)); conn.execute('DELETE FROM students WHERE id=?',(id,)); conn.commit(); conn.close()
    flash('Öğrenci ve kitapları silindi.','info'); return redirect(url_for('admin'))

@app.route('/admin/add',methods=['POST'])
@login_required
def add_book():
    f=request.form
    try:
        conn=db(); conn.execute('''INSERT INTO books(student_id,title,author,page_count,issue_date,return_date)
                                   VALUES(?,?,?,?,?,?)''',(int(f['student_id']),f['title'].strip(),f['author'].strip(),int(f['page_count']),f['issue_date'],f['return_date']))
        conn.commit(); conn.close(); flash('Kitap başarıyla eklendi!','success')
    except Exception as e: flash('Kitap eklenemedi.','error')
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:id>',methods=['POST'])
@login_required
def delete_book(id):
    conn=db(); conn.execute('DELETE FROM books WHERE id=?',(id,)); conn.commit(); conn.close(); flash('Kitap silindi.','info'); return redirect(url_for('admin'))

init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=5000)
