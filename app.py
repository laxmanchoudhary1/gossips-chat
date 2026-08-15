import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'gossips_chat_super_secret_key'
socketio = SocketIO(app)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
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
    conn.close()

init_db()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('signup'))
        hashed_password = generate_password_hash(password)
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            conn.close()
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists! Choose another.', 'error')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['username'] = user[1]
            return redirect(url_for('chat'))
        else:
            flash('Invalid username or incorrect password!', 'error')
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
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE name = ?', (room,))
    group = cursor.fetchone()
    if group:
        if group[2] == password:
            join_room(room)
            emit('join_status', {'status': 'success', 'room': room}, room=request.sid)
            emit('message', {'username': 'System', 'msg': f'{username} has joined the room.'}, room=room)
        else:
            emit('join_status', {'status': 'error', 'msg': 'Incorrect group password! Access denied.'}, room=request.sid)
    else:
        cursor.execute('INSERT INTO groups (name, password) VALUES (?, ?)', (room, password))
        conn.commit()
        join_room(room)
        emit('join_status', {'status': 'success', 'room': room}, room=request.sid)
        emit('message', {'username': 'System', 'msg': f'Group "{room}" created and {username} joined.'}, room=room)
    conn.close()

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    username = data['username']
    msg = data['msg']
    emit('message', {'username': username, 'msg': msg}, room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
