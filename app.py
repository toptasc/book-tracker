import os
import sqlite3
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key-change-this-in-prod')

# Admin Kullanıcı Ayarları (Env üzerinden de verilebilir)
ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'veli')
# Varsayılan şifre: veli123
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASS', 'veli123'))

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'books.db')

def init_db():
    """Veritabanını ve tabloyu oluşturur."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

# Uygulama başlarken DB'yi hazırla
init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books ORDER BY id DESC').fetchall()
    
    # İstatistikler
    total_books = len(books)
    total_pages = sum(book['page_count'] for book in books) if books else 0
    
    conn.close()
    return render_template('index.html', books=books, total_books=total_books, total_pages=total_pages)

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
    conn.close()
    return render_template('admin.html', books=books)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_book():
    title = request.form.get('title')
    author = request.form.get('author')
    page_count = request.form.get('page_count')
    issue_date = request.form.get('issue_date')
    return_date = request.form.get('return_date')
    
    if title and author and page_count and issue_date and return_date:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO books (title, author, page_count, issue_date, return_date) VALUES (?, ?, ?, ?, ?)',
            (title, author, int(page_count), issue_date, return_date)
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