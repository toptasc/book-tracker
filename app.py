import os
import sqlite3
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key-change-this-in-prod')

ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'veli')
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASS', 'veli123'))

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'books.db')

# Rütbe Hesaplama Mantığı
RANKS = [
    (0, "Acemi Okuyucu", "bg-slate-100 text-slate-700 border-slate-300", "fa-user-ninja"),
    (5, "Onbaşı", "bg-blue-100 text-blue-800 border-blue-300", "fa-award"),
    (10, "Çavuş", "bg-emerald-100 text-emerald-800 border-emerald-300", "fa-certificate"),
    (15, "Teğmen", "bg-purple-100 text-purple-800 border-purple-300", "fa-star"),
    (20, "Yüzbaşı", "bg-amber-100 text-amber-800 border-amber-300", "fa-medal"),
    (25, "Binbaşı", "bg-orange-100 text-orange-800 border-orange-300", "fa-crown"),
    (30, "Albay", "bg-rose-100 text-rose-800 border-rose-300", "fa-trophy"),
]

def get_rank(book_count):
    current_rank = RANKS[0]
    next_rank_count = RANKS[1][0]
    
    for i, rank in enumerate(RANKS):
        if book_count >= rank[0]:
            current_rank = rank
            if i + 1 < len(RANKS):
                next_rank_count = RANKS[i + 1][0]
            else:
                next_rank_count = None
                
    return {
        "title": current_rank[1],
        "badge_style": current_rank[2],
        "icon": current_rank[3],
        "next_count": next_rank_count
    }

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    
    # Tüm kitapları getir
    all_books = conn.execute('SELECT * FROM books ORDER BY id DESC').fetchall()
    
    # Öğrencilere göre kitapları grupla
    students_data = {}
    total_class_books = len(all_books)
    total_class_pages = sum(b['page_count'] for b in all_books) if all_books else 0
    
    for book in all_books:
        name = book['student_name'].strip()
        if name not in students_data:
            students_data[name] = {
                'name': name,
                'books': [],
                'total_pages': 0
            }
        students_data[name]['books'].append(book)
        students_data[name]['total_pages'] += book['page_count']
    
    # Öğrencilerin rütbelerini hesapla
    students_list = []
    for name, data in students_data.items():
        book_count = len(data['books'])
        rank_info = get_rank(book_count)
        
        # Sonraki rütbeye ilerleme yüzdesi
        progress = 100
        if rank_info['next_count']:
            progress = int((book_count / rank_info['next_count']) * 100)
            
        students_list.append({
            'name': name,
            'books': data['books'],
            'book_count': book_count,
            'total_pages': data['total_pages'],
            'rank': rank_info,
            'progress': progress
        })
    
    # En çok kitap okuyana göre sırala
    students_list.sort(key=lambda x: x['book_count'], reverse=True)
    
    conn.close()
    return render_template(
        'index.html', 
        students=students_list, 
        total_class_books=total_class_books, 
        total_class_pages=total_class_pages
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['is_admin'] = True
            session['username'] = username
            flash('Başarıyla giriş yaptınız.', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Oturum kapatıldı.', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books ORDER BY id DESC').fetchall()
    
    # Açılır listede kolay seçim için mevcut öğrencilerin isimleri
    existing_students = conn.execute('SELECT DISTINCT student_name FROM books ORDER BY student_name ASC').fetchall()
    conn.close()
    return render_template('admin.html', books=books, existing_students=existing_students)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_book():
    student_name = request.form.get('student_name_custom') or request.form.get('student_name_select')
    title = request.form.get('title')
    author = request.form.get('author')
    page_count = request.form.get('page_count')
    issue_date = request.form.get('issue_date')
    return_date = request.form.get('return_date')
    
    if student_name and title and author and page_count and issue_date and return_date:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO books (student_name, title, author, page_count, issue_date, return_date) VALUES (?, ?, ?, ?, ?, ?)',
            (student_name.strip().title(), title.strip(), author.strip(), int(page_count), issue_date, return_date)
        )
        conn.commit()
        conn.close()
        flash('Kitap başarıyla eklendi!', 'success')
    else:
        flash('Lütfen tüm alanları doldurun.', 'error')
        
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def delete_book(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM books WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Kitap silindi.', 'info')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)