# 🎮 TriviaBlast - Multiplayer Trivia Game

A Kahoot-style multiplayer trivia game built with Flask + Socket.IO.

## 🚀 How to Start

Double-click **`start.bat`** or run in terminal:
```
cd trivia-game
uv run python app.py
```
Then open **http://localhost:5000** in your browser.

---

## 🎯 How to Play

### Host
1. Go to `http://localhost:5000`
2. Click **"Create Session"** — a 6-character code is generated
3. Share the code with players
4. Click **"Open Host Dashboard"** → **"Join as Host"**
5. Wait for players to join, then click **"Start Game!"**
6. After each question's timer ends, click **"Next Question"**

### Players
1. Go to `http://localhost:5000`
2. Enter the session code + your username → **"Join Game"**
3. Wait in the lobby until the host starts
4. Answer each question within **15 seconds**
5. Faster correct answers = more points (up to 1000 pts)

---

## 📋 Game Features

- ✅ Real-time multiplayer via WebSockets
- ✅ 25 randomly selected questions per session
- ✅ 15-second countdown timer per question
- ✅ Speed-based scoring (max 1000 pts per question)
- ✅ Live leaderboard between questions
- ✅ Visual images for each question (via Unsplash)
- ✅ Final podium + full rankings
- ✅ All scores logged to SQLite database

---

## 📁 Project Structure

```
trivia-game/
├── app.py              # Flask + SocketIO server
├── database.py         # SQLite database functions
├── questions.json      # Trivia question bank
├── pyproject.toml      # Python dependencies
├── start.bat           # Windows startup script
├── static/
│   ├── css/style.css   # Kahoot-like styling
│   └── js/game.js      # Client-side game logic
└── templates/
    ├── index.html      # Home page
    ├── lobby.html      # Join/waiting room
    ├── game.html       # Game screen
    └── results.html    # Final results
```

---

## 🗄️ Database

Game logs are stored in `trivia_game.db` (SQLite):
- **sessions** — session ID, status, timestamps
- **players** — username, session, final score
- **game_log** — per-question answers, correctness, points

---

## ➕ Adding More Questions

Edit `questions.json` and add entries in this format:
```json
{
  "id": 51,
  "question": "Your question here?",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "answer": "Option A",
  "keyword": "search keyword for image"
}
```
