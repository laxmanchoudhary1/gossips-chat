import sqlite3
import re
import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'syncsphere_super_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app)
room_users = {} # room -> set of usernames

def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                mobile TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'Online 🟢'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT NOT NULL,
                username TEXT NOT NULL,
                msg TEXT NOT NULL,
                file_url TEXT,
                file_name TEXT,
                audio_url TEXT,
                reactions TEXT DEFAULT '{}',
                is_pinned INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT NOT NULL,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                votes TEXT DEFAULT '{}',
                creator TEXT NOT NULL
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
                    flash('Username already taken!', 'error')
                    return redirect(url_for('signup'))
                
                cursor.execute('SELECT id FROM users WHERE mobile = ?', (mobile,))
                if cursor.fetchone():
                    flash('Mobile number already registered!', 'error')
                    return redirect(url_for('signup'))
                
                cursor.execute('INSERT INTO users (username, password, mobile) VALUES (?, ?, ?)', (username, hashed_password, mobile))
                conn.commit()
                
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or Mobile already exists!', 'error')
            return redirect(url_for('signup'))
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        mobile = request.form.get('mobile', '').strip()
        password = request.form['password'].strip()
        
        if not password or (not username and not mobile):
            flash('Please provide password and identifier!', 'error')
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
            flash('Invalid credentials or password!', 'error')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, mobile, status FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
    if request.method == 'POST':
        if 'update_status' in request.form:
            new_status = request.form['status'].strip()
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET status = ? WHERE username = ?', (new_status, username))
                conn.commit()
            flash('Status updated successfully!', 'success')
        else:
            old_pass = request.form['old_password'].strip()
            new_pass = request.form['new_password'].strip()
            
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
                db_pass = cursor.fetchone()[0]
                
            if check_password_hash(db_pass, old_pass):
                hashed_new = generate_password_hash(new_pass)
                with sqlite3.connect('database.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET password = ? WHERE username = ?', (hashed_new, username))
                    conn.commit()
                flash('Password updated successfully!', 'success')
            else:
                flash('Incorrect old password!', 'error')
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=user_data)

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
    password = data.get('password', '').strip()
    is_dm = data.get('is_dm', False)
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM users WHERE username = ?', (username,))
        user_status_row = cursor.fetchone()
        user_status = user_status_row[0] if user_status_row else 'Online 🟢'

        if is_dm:
            join_room(room)
            if room not in room_users:
                room_users[room] = {}
            room_users[room][username] = user_status
            
            cursor.execute('SELECT id, username, msg, file_url, file_name, audio_url, reactions, is_pinned FROM messages WHERE room = ? ORDER BY id ASC LIMIT 50', (room,))
            history = [{
                'id': row[0], 'username': row[1], 'msg': row[2], 
                'file_url': row[3], 'file_name': row[4], 'audio_url': row[5], 'reactions': row[6], 'is_pinned': row[7]
            } for row in cursor.fetchall()]

            emit('join_status', {'status': 'success', 'room': room, 'is_dm': True, 'history': history, 'polls': []}, room=request.sid)
            return

        cursor.execute('SELECT * FROM groups WHERE name = ?', (room,))
        group = cursor.fetchone()
        
        if group:
            if group[2] == password:
                join_room(room)
                if room not in room_users:
                    room_users[room] = {}
                room_users[room][username] = user_status
                
                cursor.execute('SELECT id, username, msg, file_url, file_name, audio_url, reactions, is_pinned FROM messages WHERE room = ? ORDER BY id ASC LIMIT 50', (room,))
                history = [{
                    'id': row[0], 'username': row[1], 'msg': row[2], 
                    'file_url': row[3], 'file_name': row[4], 'audio_url': row[5], 'reactions': row[6], 'is_pinned': row[7]
                } for row in cursor.fetchall()]

                cursor.execute('SELECT id, question, options, votes, creator FROM polls WHERE room = ?', (room,))
                polls = [{
                    'id': p[0], 'question': p[1], 'options': json.loads(p[2]), 'votes': json.loads(p[3]), 'creator': p[4]
                } for p in cursor.fetchall()]
                
                emit('join_status', {'status': 'success', 'room': room, 'is_dm': False, 'password': group[2], 'history': history, 'polls': polls}, room=request.sid)
                emit('room_users', {'users': room_users[room]}, room=room)
                emit('message', {'username': 'System', 'msg': f'{username} joined the room.'}, room=room)
            else:
                emit('join_status', {'status': 'error', 'msg': 'Wrong group password!'}, room=request.sid)
        else:
            cursor.execute('INSERT INTO groups (name, password) VALUES (?, ?)', (room, password))
            conn.commit()
            join_room(room)
            if room not in room_users:
                room_users[room] = {}
            room_users[room][username] = user_status
            
            emit('join_status', {'status': 'success', 'room': room, 'is_dm': False, 'password': password, 'history': [], 'polls': []}, room=request.sid)
            emit('room_users', {'users': room_users[room]}, room=room)
            emit('message', {'username': 'System', 'msg': f'Group created and {username} joined.'}, room=room)

@socketio.on('leave_group')
def handle_leave(data):
    room = data['room']
    username = data['username']
    leave_room(room)
    if room in room_users and username in room_users[room]:
        del room_users[room][username]
        emit('room_users', {'users': room_users[room]}, room=room)
    emit('message', {'username': 'System', 'msg': f'{username} left the room.'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    username = data['username']
    msg = data.get('msg', '')
    file_url = data.get('file_url')
    file_name = data.get('file_name')
    audio_url = data.get('audio_url')
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (room, username, msg, file_url, file_name, audio_url, reactions, is_pinned) 
            VALUES (?, ?, ?, ?, ?, ?, '{}', 0)
        ''', (room, username, msg, file_url, file_name, audio_url))
        conn.commit()
        msg_id = cursor.lastrowid
        
    emit('message', {
        'id': msg_id, 'username': username, 'msg': msg, 
        'file_url': file_url, 'file_name': file_name, 'audio_url': audio_url, 'reactions': {}, 'is_pinned': 0
    }, room=room)

@socketio.on('create_poll')
def handle_create_poll(data):
    room = data['room']
    question = data['question']
    options = data['options']
    username = data['username']
    
    initial_votes = {opt: [] for opt in options}
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO polls (room, question, options, votes, creator) VALUES (?, ?, ?, ?, ?)',
                       (room, question, json.dumps(options), json.dumps(initial_votes), username))
        conn.commit()
        poll_id = cursor.lastrowid
        
    emit('new_poll', {
        'id': poll_id, 'question': question, 'options': options, 'votes': initial_votes, 'creator': username
    }, room=room)

@socketio.on('vote_poll')
def handle_vote_poll(data):
    poll_id = data['poll_id']
    option = data['option']
    username = data['username']
    room = data['room']
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT options, votes FROM polls WHERE id = ?', (poll_id,))
        row = cursor.fetchone()
        if row:
            options = json.loads(row[0])
            votes = json.loads(row[1])
            
            for opt in options:
                if username in votes[opt]:
                    votes[opt].remove(username)
            
            if option in votes:
                votes[option].append(username)
                
            cursor.execute('UPDATE polls SET votes = ? WHERE id = ?', (json.dumps(votes), poll_id))
            conn.commit()
            
            emit('update_poll', {'poll_id': poll_id, 'votes': votes}, room=room)

@socketio.on('add_reaction')
def handle_reaction(data):
    msg_id = data['msg_id']
    emoji = data['emoji']
    username = data['username']
    room = data['room']
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT reactions FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        if row:
            reactions = json.loads(row[0] or '{}')
            if emoji not in reactions:
                reactions[emoji] = []
            if username in reactions[emoji]:
                reactions[emoji].remove(username)
                if not reactions[emoji]:
                    del reactions[emoji]
            else:
                reactions[emoji].append(username)
            
            new_react_str = json.dumps(reactions)
            cursor.execute('UPDATE messages SET reactions = ? WHERE id = ?', (new_react_str, msg_id))
            conn.commit()
            
            emit('update_reaction', {'msg_id': msg_id, 'reactions': reactions}, room=room)

@socketio.on('toggle_pin')
def handle_pin(data):
    msg_id = data['msg_id']
    room = data['room']
    is_pinned = data['is_pinned']
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE messages SET is_pinned = ? WHERE id = ?', (1 if is_pinned else 0, msg_id))
        conn.commit()
        
    emit('update_pin', {'msg_id': msg_id, 'is_pinned': is_pinned}, room=room)

@socketio.on('typing')
def handle_typing(data):
    emit('display_typing', {'username': data['username'], 'is_typing': data['is_typing']}, room=data['room'], include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
