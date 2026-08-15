import sqlite3
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
        
        hashed_password = generate_password_hash(password)
        try:
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (username, password, mobile) VALUES (?, ?, ?)', (username, hashed_password, mobile))
                conn.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or Mobile already taken!', 'error')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Dono fields le lo
        username = request.form.get('username', '').strip()
        mobile = request.form.get('mobile', '').strip()
        password = request.form['password'].strip()
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            # Ya to username se ya mobile se check karo
            cursor.execute('SELECT * FROM users WHERE username = ? OR mobile = ?', (username, mobile))
            user = cursor.fetchone()
            
        if user and check_password_hash(user[2], password):
            session['username'] = user[1]
            return redirect(url_for('chat'))
        else:
            flash('Invalid details or password!', 'error')
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
            if check_password_hash(group[2], password):
                join_room(room)
                emit('join_status', {'status': 'success', 'room': room}, room=request.sid)
                emit('message', {'username': 'System', 'msg': f'{username} joined.'}, room=room)
            else:
                emit('join_status', {'status': 'error', 'msg': 'Wrong password!'}, room=request.sid)
        else:
            hashed_pass = generate_password_hash(password)
            cursor.execute('INSERT INTO groups (name, password) VALUES (?, ?)', (room, hashed_pass))
            conn.commit()
            join_room(room)
            emit('join_status', {'status': 'success', 'room': room}, room=request.sid)
            emit('message', {'username': 'System', 'msg': f'Group created by {username}'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    emit('message', {'username': data['username'], 'msg': data['msg']}, room=data['room'])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
