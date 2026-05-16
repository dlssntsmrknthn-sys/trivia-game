import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'trivia_game.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'waiting',
            total_questions INTEGER DEFAULT 25
        );

        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            username TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            joined_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS game_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            username TEXT NOT NULL,
            question_number INTEGER NOT NULL,
            question_text TEXT,
            selected_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER DEFAULT 0,
            time_taken REAL DEFAULT 0,
            points_earned INTEGER DEFAULT 0,
            logged_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
    ''')

    conn.commit()
    conn.close()

def create_session(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO sessions (session_id, created_at, status) VALUES (?, ?, ?)',
        (session_id, datetime.now().isoformat(), 'waiting')
    )
    conn.commit()
    conn.close()

def get_session(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_session_status(session_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE sessions SET status = ? WHERE session_id = ?', (status, session_id))
    conn.commit()
    conn.close()

def add_player(session_id, username):
    conn = get_db()
    cursor = conn.cursor()
    # Check if player already exists
    cursor.execute('SELECT id FROM players WHERE session_id = ? AND username = ?', (session_id, username))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return False
    cursor.execute(
        'INSERT INTO players (session_id, username, score, joined_at) VALUES (?, ?, 0, ?)',
        (session_id, username, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return True

def get_players(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT username, score FROM players WHERE session_id = ? ORDER BY score DESC',
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_player_score(session_id, username, points):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE players SET score = score + ? WHERE session_id = ? AND username = ?',
        (points, session_id, username)
    )
    conn.commit()
    conn.close()

def log_answer(session_id, username, question_number, question_text, selected_answer, correct_answer, is_correct, time_taken, points_earned):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO game_log 
           (session_id, username, question_number, question_text, selected_answer, correct_answer, is_correct, time_taken, points_earned, logged_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (session_id, username, question_number, question_text, selected_answer, correct_answer,
         1 if is_correct else 0, time_taken, points_earned, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_final_scores(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT username, score FROM players WHERE session_id = ? ORDER BY score DESC',
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_sessions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
