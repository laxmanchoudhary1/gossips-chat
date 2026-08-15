import os
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gossips Chat - Multiuser & AI</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body class="h-full bg-slate-950 text-slate-100 font-sans antialiased overflow-hidden flex flex-col">
    <header class="flex items-center justify-between px-6 py-4 bg-slate-900 border-b border-slate-800 z-40 shrink-0">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-600/30">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
            </div>
            <div>
                <h1 class="text-base font-bold tracking-tight">Gossips Chat</h1>
                <p class="text-[10px] text-slate-400">Multi-User & AI Experience</p>
            </div>
        </div>
        <div class="flex items-center space-x-3">
            <button onclick="openAuthModal()" class="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold shadow-md transition-all">
                🔐 Sign In / Lookup
            </button>
            <div id="user-badge" class="hidden items-center space-x-3 bg-slate-800 px-3.5 py-1.5 rounded-xl border border-slate-700">
                <div class="text-right">
                    <p class="text-xs font-bold text-indigo-400" id="badge-name">-</p>
                    <p class="text-[10px] text-slate-400" id="badge-phone">-</p>
                </div>
                <button onclick="logoutUser()" class="text-xs text-red-400 hover:text-red-300 ml-1 bg-slate-900 px-2.5 py-1 rounded-lg">Logout</button>
            </div>
        </div>
    </header>

    <div id="auth-modal" class="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-3xl p-6 w-full max-w-md shadow-2xl space-y-5">
            <div class="text-center">
                <h2 class="text-xl font-bold">Account Access & Lookup</h2>
                <p class="text-xs text-slate-400 mt-1">Enter phone number to lookup or create your account</p>
            </div>
            <form id="auth-form" class="space-y-3.5">
                <div>
                    <label class="block text-xs font-medium text-slate-400 mb-1">Phone Number (Account ID)</label>
                    <input type="tel" id="lookup-phone" required placeholder="e.g. 9876543210" class="w-full bg-slate-950 text-slate-100 placeholder-slate-600 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-400 mb-1">Your Name</label>
                    <input type="text" id="lookup-name" required placeholder="e.g. Aryan" class="w-full bg-slate-950 text-slate-100 placeholder-slate-600 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-400 mb-1">Password</label>
                    <input type="password" id="lookup-pass" required placeholder="••••••••" class="w-full bg-slate-950 text-slate-100 placeholder-slate-600 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-indigo-500">
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-xl font-medium text-sm transition-all shadow-lg shadow-indigo-600/25">
                    Continue / Search Number
                </button>
            </form>
        </div>
    </div>

    <div id="group-container" class="flex-1 flex flex-col justify-center items-center p-4 overflow-y-auto">
        <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
            <div class="text-center">
                <span class="text-xs font-semibold px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">Step 2</span>
                <h2 class="text-xl font-bold mt-2">Join Room / Group</h2>
                <p class="text-xs text-slate-400">Multiple users can join the same group to talk</p>
            </div>
            <form id="group-form" class="space-y-4">
                <div>
                    <label class="block text-xs font-medium text-slate-400 mb-1">Group / Room Name</label>
                    <input type="text" id="group-input" required value="GossipsLobby" class="w-full bg-slate-950 text-slate-100 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-indigo-500">
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-xl font-medium text-sm transition-all shadow-lg shadow-indigo-600/25">
                    Enter Group Chat 🚀
                </button>
            </form>
        </div>
    </div>

    <div id="main-chat-app" class="hidden flex-1 flex flex-row w-full overflow-hidden">
        <aside class="w-72 bg-slate-900 border-r border-slate-800 flex flex-col justify-between hidden md:flex shrink-0">
            <div>
                <div class="p-4 border-b border-slate-800">
                    <h2 class="font-bold text-xs uppercase tracking-wider text-slate-400">Active Room</h2>
                    <p class="font-extrabold text-sm text-indigo-400 mt-0.5" id="sidebar-group-name">GossipsLobby</p>
                </div>
                <div class="p-3 space-y-2">
                    <button onclick="switchTab('group')" id="tab-btn-group" class="w-full flex items-center space-x-3 px-3.5 py-3 rounded-xl bg-indigo-600 text-white text-xs font-semibold transition-all shadow-md">
                        <span>👥</span>
                        <span>Group Live Chat</span>
                    </button>
                    <button onclick="switchTab('ai')" id="tab-btn-ai" class="w-full flex items-center space-x-3 px-3.5 py-3 rounded-xl bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition-all border border-slate-800">
                        <span>🤖</span>
                        <span>Dedicated AI Assistant</span>
                    </button>
                </div>
            </div>
            <div class="p-4 border-t border-slate-800">
                <p class="text-[11px] text-slate-500 text-center">Connected securely via WebSockets & Gemini AI</p>
            </div>
        </aside>

        <div class="flex-1 flex flex-col h-full bg-slate-950 overflow-hidden">
            <header class="flex items-center justify-between px-6 py-3.5 bg-slate-900 border-b border-slate-800 shrink-0">
                <div class="flex items-center space-x-3">
                    <div class="md:hidden flex space-x-2">
                        <button onclick="switchTab('group')" class="px-2.5 py-1 bg-indigo-600 text-white text-[11px] rounded-lg">Group</button>
                        <button onclick="switchTab('ai')" class="px-2.5 py-1 bg-slate-800 text-slate-300 text-[11px] rounded-lg">AI</button>
                    </div>
                    <h2 class="font-bold text-sm text-slate-100" id="current-chat-title">Group Live Chat</h2>
                </div>
                <span class="text-xs text-emerald-400 flex items-center space-x-1.5 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span>Online</span>
                </span>
            </header>

            <div id="view-group-chat" class="flex-1 flex flex-col overflow-hidden">
                <div id="group-chat-container" class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3"></div>
                <footer class="p-4 bg-slate-900 border-t border-slate-800 shrink-0">
                    <form id="group-chat-form" class="max-w-4xl mx-auto flex items-center gap-3">
                        <input type="text" id="group-msg-input" placeholder="Message group members..." required class="w-full bg-slate-950 text-slate-100 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-indigo-500">
                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-3 rounded-xl font-medium text-sm">Send</button>
                    </form>
                </footer>
            </div>

            <div id="view-ai-chat" class="hidden flex-1 flex flex-col overflow-hidden">
                <div id="ai-chat-container" class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3">
                    <div class="flex justify-start">
                        <div class="max-w-[75%] rounded-2xl p-4 bg-slate-900 text-slate-200 border border-slate-800">
                            <p class="text-xs font-bold text-indigo-400 mb-1">Dedicated AI Assistant</p>
                            <p class="text-sm">Hello! Ask me anything directly. This chat is separate from your group conversation.</p>
                        </div>
                    </div>
                </div>
                <footer class="p-4 bg-slate-900 border-t border-slate-800 shrink-0">
                    <form id="ai-chat-form" class="max-w-4xl mx-auto flex items-center gap-3">
                        <input type="text" id="ai-msg-input" placeholder="Ask Gemini AI anything..." required class="w-full bg-slate-950 text-slate-100 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-indigo-500">
                        <button type="submit" class="bg-violet-600 hover:bg-violet-500 text-white px-5 py-3 rounded-xl font-medium text-sm">Ask AI</button>
                    </form>
                </footer>
            </div>
        </div>
    </div>

    <script>
        let currentUser = JSON.parse(localStorage.getItem('gossips_user')) || null;
        let currentGroup = "GossipsLobby";
        let socket = null;

        function checkAuthState() {
            if (currentUser) {
                document.getElementById('auth-modal').classList.add('hidden');
                document.getElementById('user-badge').classList.remove('hidden');
                document.getElementById('badge-name').innerText = currentUser.name;
                document.getElementById('badge-phone').innerText = currentUser.phone;
            } else {
                document.getElementById('auth-modal').classList.remove('hidden');
                document.getElementById('user-badge').classList.add('hidden');
            }
        }

        function openAuthModal() {
            document.getElementById('auth-modal').classList.remove('hidden');
        }

        function logoutUser() {
            localStorage.removeItem('gossips_user');
            currentUser = null;
            window.location.reload();
        }

        document.getElementById('auth-form').addEventListener('submit', function(e) {
            e.preventDefault();
            const phone = document.getElementById('lookup-phone').value.trim();
            const name = document.getElementById('lookup-name').value.trim();
            const pass = document.getElementById('lookup-pass').value.trim();

            let allAccounts = JSON.parse(localStorage.getItem('gossips_accounts')) || {};

            if (allAccounts[phone]) {
                currentUser = allAccounts[phone];
                alert('Account found and loaded for number: ' + phone + ' (' + currentUser.name + ')');
            } else {
                currentUser = { phone, name, pass };
                allAccounts[phone] = currentUser;
                localStorage.setItem('gossips_accounts', JSON.stringify(allAccounts));
                alert('New account created and saved successfully for number: ' + phone);
            }

            localStorage.setItem('gossips_user', JSON.stringify(currentUser));
            checkAuthState();
        });

        document.getElementById('group-form').addEventListener('submit', function(e) {
            e.preventDefault();
            if (!currentUser) {
                alert('Please sign in or lookup your account first!');
                openAuthModal();
                return;
            }
            currentGroup = document.getElementById('group-input').value.trim() || "GossipsLobby";
            
            document.getElementById('group-container').style.display = 'none';
            document.getElementById('main-chat-app').classList.remove('hidden');
            document.getElementById('sidebar-group-name').innerText = currentGroup;

            initSocketConnection();
        });

        function switchTab(tab) {
            const groupView = document.getElementById('view-group-chat');
            const aiView = document.getElementById('view-ai-chat');
            const groupBtn = document.getElementById('tab-btn-group');
            const aiBtn = document.getElementById('tab-btn-ai');
            const title = document.getElementById('current-chat-title');

            if (tab === 'group') {
                groupView.classList.remove('hidden');
                aiView.classList.add('hidden');
                groupBtn.className = "w-full flex items-center space-x-3 px-3.5 py-3 rounded-xl bg-indigo-600 text-white text-xs font-semibold transition-all shadow-md";
                aiBtn.className = "w-full flex items-center space-x-3 px-3.5 py-3 rounded-xl bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition-all border border-slate-800";
                title.innerText = "Group Live Chat (" + currentGroup + ")";
            } else {
                groupView.classList.add('hidden');
                aiView.classList.remove('hidden');
                aiBtn.className = "w-full flex items-center space-x-3 px-3.5 py-3 rounded-xl bg-violet-600 text-white text-xs font-semibold transition-all shadow-md";
                groupBtn.className = "w-full flex items-center space-x-3 px-3.5 py-3 rounded-xl bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition-all border border-slate-800";
                title.innerText = "Dedicated AI Assistant (Gemini)";
            }
        }

        function initSocketConnection() {
            socket = io();
            socket.emit('join_room', { username: currentUser.name, room: currentGroup });

            socket.on('message', function(data) {
                appendGroupMessage(data.username, data.message, data.username === currentUser.name);
            });

            socket.on('room_notification', function(data) {
                appendSystemMessage(data.message);
            });
        }

        const groupChatContainer = document.getElementById('group-chat-container');
        function appendGroupMessage(sender, text, isSelf) {
            const div = document.createElement('div');
            div.className = `flex ${isSelf ? 'justify-end' : 'justify-start'}`;
            div.innerHTML = `
                <div class="max-w-[70%] rounded-2xl p-3.5 ${isSelf ? 'bg-indigo-600 text-white' : 'bg-slate-900 text-slate-200 border border-slate-800'}">
                    <p class="text-[10px] font-bold opacity-75 mb-0.5">${sender}</p>
                    <p class="text-sm">${text}</p>
                </div>
            `;
            groupChatContainer.appendChild(div);
            groupChatContainer.scrollTop = groupChatContainer.scrollHeight;
        }

        function appendSystemMessage(text) {
            const div = document.createElement('div');
            div.className = 'flex justify-center my-2';
            div.innerHTML = `<span class="text-[11px] bg-slate-900 text-slate-400 px-3 py-1 rounded-full border border-slate-800">${text}</span>`;
            groupChatContainer.appendChild(div);
            groupChatContainer.scrollTop = groupChatContainer.scrollHeight;
        }

        document.getElementById('group-chat-form').addEventListener('submit', function(e) {
            e.preventDefault();
            const input = document.getElementById('group-msg-input');
            const text = input.value.trim();
            if (!text || !socket) return;

            socket.emit('send_message', { username: currentUser.name, room: currentGroup, message: text });
            input.value = '';
        });

        const aiChatContainer = document.getElementById('ai-chat-container');
        document.getElementById('ai-chat-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const input = document.getElementById('ai-msg-input');
            const text = input.value.trim();
            if (!text) return;

            const userDiv = document.createElement('div');
            userDiv.className = 'flex justify-end';
            userDiv.innerHTML = `
                <div class="max-w-[75%] rounded-2xl p-3.5 bg-violet-600 text-white">
                    <p class="text-[10px] font-bold opacity-75 mb-0.5">You</p>
                    <p class="text-sm">${text}</p>
                </div>
            `;
            aiChatContainer.appendChild(userDiv);
            aiChatContainer.scrollTop = aiChatContainer.scrollHeight;
            input.value = '';

            try {
                const response = await fetch('/api/ai-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: text })
                });
                const data = await response.json();
                
                const aiDiv = document.createElement('div');
                aiDiv.className = 'flex justify-start';
                aiDiv.innerHTML = `
                    <div class="max-w-[75%] rounded-2xl p-3.5 bg-slate-900 text-slate-200 border border-slate-800">
                        <p class="text-[10px] font-bold text-violet-400 mb-0.5">Dedicated AI Assistant</p>
                        <p class="text-sm">${data.reply}</p>
                    </div>
                `;
                aiChatContainer.appendChild(aiDiv);
                aiChatContainer.scrollTop = aiChatContainer.scrollHeight;
            } catch (err) {
                const errDiv = document.createElement('div');
                errDiv.className = 'flex justify-start';
                errDiv.innerHTML = `<div class="p-3 bg-red-950 text-red-300 rounded-xl text-xs">⚠️ Error fetching AI response.</div>`;
                aiChatContainer.appendChild(errDiv);
            }
        });

        checkAuthState();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    data = request.get_json()
    user_prompt = data.get('prompt', '')
    
    if not GEMINI_API_KEY:
        return jsonify({"reply": f"⚠️ Gemini API Key not set! Run: export GEMINI_API_KEY='your_key'. Echo: {user_prompt}"})
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'Application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": user_prompt}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        ai_response = res_data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        ai_response = f"Error communicating with Gemini API: {str(e)}"
        
    return jsonify({"reply": ai_response})

@socketio.on('join_room')
def handle_join(data):
    room = data.get('room')
    username = data.get('username')
    join_room(room)
    emit('room_notification', {'message': f'{username} joined the room.'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    room = data.get('room')
    username = data.get('username')
    message = data.get('message')
    emit('message', {'username': username, 'message': message}, room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
