import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'gossips_chat_super_secret_key'
socketio = SocketIO(app)

def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                mobile TEXT UNIQUE NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()

init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        mobile = request.form['mobile'].strip()
        password = request.form['password'].strip()
        
        if not username or not mobile or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('signup'))
            
        if not re.match(r'^\d{10}$', mobile):
            flash('Mobile number must be exactly 10 digits!', 'error')
            return redirect(url_for('signup'))
            
        hashed_password = generate_password_hash(password)
        try:
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                if cursor.fetchone():
                    flash('Username already taken! Choose another one.', 'error')
                    return redirect(url_for('signup'))
                
                cursor.execute('SELECT id FROM users WHERE mobile = ?', (mobile,))
                if cursor.fetchone():
                    flash('Mobile number already registered with an account!', 'error')
                    return redirect(url_for('signup'))
                
                cursor.execute('INSERT INTO users (username, password, mobile) VALUES (?, ?, ?)', (username, hashed_password, mobile))
                conn.commit()
                
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or Mobile number already exists!', 'error')
            return redirect(url_for('signup'))
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        mobile = request.form.get('mobile', '').strip()
        password = request.form['password'].strip()
        
        if not password or (not username and not mobile):
            flash('Please provide password and either username or mobile number!', 'error')
            return redirect(url_for('login'))
            
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            if username:
                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            else:
                cursor.execute('SELECT * FROM users WHERE mobile = ?', (mobile,))
            user = cursor.fetchone()
            
        if user and check_password_hash(user[2], password):
            session['username'] = user[1]
            return redirect(url_for('chat'))
        else:
            flash('Invalid credentials or incorrect password!', 'error')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@socketio.on('join_group')
def handle_join(data):
    username = data['username']
    room = data['room'].strip()
    password = data['password'].strip()
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM groups WHERE name = ?', (room,))
        group = cursor.fetchone()
        
        if group:
            if group[2] == password:
                join_room(room)
                emit('join_status', {'status': 'success', 'room': room, 'password': group[2]}, room=request.sid)
                emit('message', {'username': 'System', 'msg': f'{username} joined.'}, room=room)
            else:
                emit('join_status', {'status': 'error', 'msg': 'Wrong password!'}, room=request.sid)
        else:
            cursor.execute('INSERT INTO groups (name, password) VALUES (?, ?)', (room, password))
            conn.commit()
            join_room(room)
            emit('join_status', {'status': 'success', 'room': room, 'password': password}, room=request.sid)
            emit('message', {'username': 'System', 'msg': f'Group created by {username}'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    emit('message', {'username': data['username'], 'msg': data['msg']}, room=data['room'])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
