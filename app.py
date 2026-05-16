import os
import json
import random
import string
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import database as db
import sheets_sync

app = Flask(__name__)
app.secret_key = 'trivia_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Initialize database (runs on startup whether via gunicorn or direct)
db.init_db()

# Load questions — try Google Sheets first, fall back to local JSON
print("[App] Loading questions...")
try:
    ALL_QUESTIONS = sheets_sync.load_questions_from_sheet()
except Exception as e:
    print(f"[App] Sheets error: {e}")
    ALL_QUESTIONS = None

if ALL_QUESTIONS:
    print(f"[App] ✅ Loaded {len(ALL_QUESTIONS)} questions from Google Sheets")
else:
    print("[App] ⚠️  Falling back to local questions.json")
    QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), 'questions.json')
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        ALL_QUESTIONS = json.load(f)
    print(f"[App] ✅ Loaded {len(ALL_QUESTIONS)} questions from local file")

# In-memory game state
game_sessions = {}
# Structure:
# {
#   session_id: {
#     'questions': [...],       # 25 selected questions
#     'current_q': 0,           # current question index
#     'status': 'waiting'|'playing'|'finished',
#     'host_sid': '...',        # socket id of host
#     'players': {username: score},
#     'answers_received': {username: answered},
#     'timer_started': False
#   }
# }

def generate_session_id():
    """Generate a unique 6-character alphanumeric session ID."""
    while True:
        sid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if sid not in game_sessions:
            return sid

def get_image_url(keyword):
    """Generate Unsplash image URL based on keyword."""
    encoded = keyword.replace(' ', '+')
    return f"https://source.unsplash.com/800x400/?{encoded}"

# ─── HTTP Routes ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_session', methods=['POST'])
def create_session():
    session_id = generate_session_id()
    # Select 25 random questions
    selected = random.sample(ALL_QUESTIONS, min(25, len(ALL_QUESTIONS)))
    game_sessions[session_id] = {
        'questions': selected,
        'current_q': 0,
        'status': 'waiting',
        'host_sid': None,
        'players': {},
        'answers_received': {},
        'timer_started': False
    }
    db.create_session(session_id)
    return jsonify({'session_id': session_id})

@app.route('/join/<session_id>')
def join_page(session_id):
    sess = game_sessions.get(session_id)
    if not sess:
        return render_template('index.html', error=f"Session '{session_id}' not found.")
    if sess['status'] == 'finished':
        return render_template('index.html', error=f"Session '{session_id}' has already ended.")
    return render_template('lobby.html', session_id=session_id)

@app.route('/game/<session_id>')
def game_page(session_id):
    username = request.args.get('username', '')
    if not username:
        return render_template('lobby.html', session_id=session_id, error="Username required.")
    return render_template('game.html', session_id=session_id, username=username)

@app.route('/results/<session_id>')
def results_page(session_id):
    scores = db.get_final_scores(session_id)
    return render_template('results.html', session_id=session_id, scores=scores)

@app.route('/api/scores/<session_id>')
def api_scores(session_id):
    scores = db.get_final_scores(session_id)
    return jsonify(scores)

# ─── Socket.IO Events ───────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('host_join')
def on_host_join(data):
    session_id = data.get('session_id')
    if session_id not in game_sessions:
        emit('error', {'message': 'Session not found'})
        return
    game_sessions[session_id]['host_sid'] = request.sid
    join_room(session_id)
    join_room(f"{session_id}_host")
    players = list(game_sessions[session_id]['players'].keys())
    emit('host_joined', {
        'session_id': session_id,
        'player_count': len(players),
        'players': players
    })

@socketio.on('player_join')
def on_player_join(data):
    session_id = data.get('session_id')
    username = data.get('username', '').strip()

    if not session_id or not username:
        emit('join_error', {'message': 'Session ID and username are required.'})
        return

    if session_id not in game_sessions:
        emit('join_error', {'message': f"Session '{session_id}' not found."})
        return

    sess = game_sessions[session_id]

    if sess['status'] == 'playing':
        emit('join_error', {'message': 'Game already in progress.'})
        return

    if sess['status'] == 'finished':
        emit('join_error', {'message': 'Game has already ended.'})
        return

    if username in sess['players']:
        emit('join_error', {'message': f"Username '{username}' is already taken."})
        return

    # Add player
    sess['players'][username] = 0
    db.add_player(session_id, username)
    join_room(session_id)

    emit('join_success', {'username': username, 'session_id': session_id})

    # Notify all in room
    players = list(sess['players'].keys())
    emit('player_list_update', {
        'players': players,
        'count': len(players)
    }, to=session_id)

@socketio.on('start_game')
def on_start_game(data):
    session_id = data.get('session_id')
    if session_id not in game_sessions:
        emit('error', {'message': 'Session not found'})
        return

    sess = game_sessions[session_id]
    if sess['status'] != 'waiting':
        emit('error', {'message': 'Game already started'})
        return

    if len(sess['players']) == 0:
        emit('error', {'message': 'No players have joined yet'})
        return

    sess['status'] = 'playing'
    sess['current_q'] = 0
    db.update_session_status(session_id, 'playing')

    emit('game_started', {'total_questions': len(sess['questions'])}, to=session_id)
    send_question(session_id)

def send_question(session_id):
    sess = game_sessions.get(session_id)
    if not sess:
        return

    q_index = sess['current_q']
    questions = sess['questions']

    if q_index >= len(questions):
        end_game(session_id)
        return

    question = questions[q_index]
    sess['answers_received'] = {}

    image_url = get_image_url(question.get('keyword', question['question']))

    socketio.emit('new_question', {
        'question_number': q_index + 1,
        'total_questions': len(questions),
        'question': question['question'],
        'options': question['options'],
        'image_url': image_url,
        'time_limit': 15
    }, to=session_id)

@socketio.on('submit_answer')
def on_submit_answer(data):
    session_id = data.get('session_id')
    username = data.get('username')
    selected = data.get('answer')
    time_taken = data.get('time_taken', 15)

    if session_id not in game_sessions:
        return

    sess = game_sessions[session_id]
    if sess['status'] != 'playing':
        return

    q_index = sess['current_q']
    question = sess['questions'][q_index]
    correct_answer = question['answer']

    # Prevent double submission
    if username in sess['answers_received']:
        return

    # Normalize answer comparison:
    # Sheet answer may be "B) Amelia Earhart" while selected is "Amelia Earhart"
    # Strip leading "X) " prefix if present for comparison
    def normalize_answer(ans):
        if ans and len(ans) > 2 and ans[1] == ')':
            return ans[2:].strip()
        return ans.strip() if ans else ans

    norm_correct = normalize_answer(correct_answer)
    norm_selected = normalize_answer(selected)
    is_correct = (norm_selected == norm_correct) or (selected == correct_answer)
    # Score: max 1000 points, scaled by speed (faster = more points)
    if is_correct:
        points = max(100, int(1000 * (1 - (time_taken / 15) * 0.5)))
    else:
        points = 0

    sess['answers_received'][username] = {
        'answer': selected,
        'is_correct': is_correct,
        'points': points,
        'time_taken': time_taken
    }

    # Update score
    sess['players'][username] = sess['players'].get(username, 0) + points
    db.update_player_score(session_id, username, points)
    db.log_answer(
        session_id, username, q_index + 1,
        question['question'], selected, correct_answer,
        is_correct, time_taken, points
    )

    # Notify player of their result
    emit('answer_result', {
        'is_correct': is_correct,
        'correct_answer': correct_answer,
        'points_earned': points,
        'total_score': sess['players'][username]
    })

    # Notify host of answer count
    total_players = len(sess['players'])
    answers_count = len(sess['answers_received'])
    socketio.emit('answer_count_update', {
        'answered': answers_count,
        'total': total_players
    }, to=f"{session_id}_host")

@socketio.on('time_up')
def on_time_up(data):
    session_id = data.get('session_id')
    if session_id not in game_sessions:
        return

    sess = game_sessions[session_id]
    if sess['status'] != 'playing':
        return

    q_index = sess['current_q']
    question = sess['questions'][q_index]
    correct_answer = question['answer']

    # Build leaderboard
    leaderboard = sorted(
        [{'username': u, 'score': s} for u, s in sess['players'].items()],
        key=lambda x: x['score'],
        reverse=True
    )

    socketio.emit('question_ended', {
        'correct_answer': correct_answer,
        'leaderboard': leaderboard[:10],
        'question_number': q_index + 1,
        'total_questions': len(sess['questions'])
    }, to=session_id)

@socketio.on('next_question')
def on_next_question(data):
    session_id = data.get('session_id')
    if session_id not in game_sessions:
        return

    sess = game_sessions[session_id]
    sess['current_q'] += 1

    if sess['current_q'] >= len(sess['questions']):
        end_game(session_id)
    else:
        send_question(session_id)

def end_game(session_id):
    sess = game_sessions.get(session_id)
    if not sess:
        return

    sess['status'] = 'finished'
    db.update_session_status(session_id, 'finished')

    final_scores = sorted(
        [{'username': u, 'score': s} for u, s in sess['players'].items()],
        key=lambda x: x['score'],
        reverse=True
    )

    socketio.emit('game_over', {
        'final_scores': final_scores,
        'session_id': session_id
    }, to=session_id)

    # Sync scores to Google Sheets (if enabled)
    sheets_sync.log_session_scores(session_id, final_scores)

@socketio.on('request_leaderboard')
def on_request_leaderboard(data):
    session_id = data.get('session_id')
    if session_id not in game_sessions:
        return
    sess = game_sessions[session_id]
    leaderboard = sorted(
        [{'username': u, 'score': s} for u, s in sess['players'].items()],
        key=lambda x: x['score'],
        reverse=True
    )
    emit('leaderboard_update', {'leaderboard': leaderboard})

if __name__ == '__main__':
    db.init_db()
    print("=" * 50)
    print("  🎮 Trivia Game Server Starting...")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
