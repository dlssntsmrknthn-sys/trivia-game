/**
 * TriviaBlast - Client-side Game Logic
 */

let socket = null;
let sessionId = '';
let username = '';
let isHost = false;
let currentScore = 0;
let timerInterval = null;
let timeLeft = 15;
let currentOptions = [];
let hasAnswered = false;
let questionStartTime = null;

const TIMER_DURATION = 15;
const LEADERBOARD_DISPLAY_TIME = 5000; // ms before auto-advancing (host only)

function initGame(sid, uname, hostMode) {
    sessionId = sid;
    username = uname;
    isHost = hostMode;

    socket = io();
    setupSocketListeners();

    // Connect and join the game room
    socket.on('connect', () => {
        console.log('Connected to game server');
        if (isHost) {
            socket.emit('host_join', { session_id: sessionId });
        } else {
            socket.emit('player_join', { session_id: sessionId, username: username });
        }
    });
}

function setupSocketListeners() {
    socket.on('join_success', (data) => {
        console.log('Joined game as player:', data.username);
        showScreen('waitingScreen');
    });

    socket.on('host_joined', (data) => {
        console.log('Joined game as host');
        showScreen('hostScreen');
        document.getElementById('hostTotal').textContent = data.player_count || 0;
    });

    socket.on('join_error', (data) => {
        alert('Error: ' + data.message);
        window.location.href = '/';
    });

    socket.on('game_started', (data) => {
        console.log('Game started! Total questions:', data.total_questions);
        currentScore = 0;
        updateScoreDisplay();
    });

    socket.on('new_question', (data) => {
        receiveQuestion(data);
    });

    socket.on('answer_result', (data) => {
        showAnswerResult(data);
    });

    socket.on('answer_count_update', (data) => {
        if (isHost) {
            document.getElementById('hostAnswered').textContent = data.answered;
            document.getElementById('hostTotal').textContent = data.total;
        }
    });

    socket.on('question_ended', (data) => {
        clearTimer();
        showLeaderboard(data);
    });

    socket.on('game_over', (data) => {
        clearTimer();
        showGameOver(data);
    });

    socket.on('player_list_update', (data) => {
        if (isHost) {
            document.getElementById('hostTotal').textContent = data.count;
        }
    });
}

// ─── Screen Management ───────────────────────────────────────────────────────

function showScreen(screenId) {
    const screens = ['waitingScreen', 'questionScreen', 'resultScreen', 'leaderboardScreen', 'hostScreen', 'gameOverScreen'];
    screens.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    const target = document.getElementById(screenId);
    if (target) target.classList.remove('hidden');
}

// ─── Question Handling ───────────────────────────────────────────────────────

function receiveQuestion(data) {
    hasAnswered = false;
    currentOptions = data.options;
    questionStartTime = Date.now();

    // Update progress
    document.getElementById('questionProgress').textContent =
        `Question ${data.question_number} / ${data.total_questions}`;

    if (isHost) {
        // Show host view
        showScreen('hostScreen');
        document.getElementById('hostQuestionText').textContent = data.question;
        document.getElementById('hostAnswered').textContent = '0';

        // Show options preview
        const preview = document.getElementById('hostOptionsPreview');
        const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12'];
        const letters = ['A', 'B', 'C', 'D'];
        preview.innerHTML = data.options.map((opt, i) =>
            `<div class="host-opt-preview" style="background:${colors[i]}">${letters[i]}. ${opt}</div>`
        ).join('');

        startHostTimer(data.time_limit || TIMER_DURATION);
    } else {
        // Show player question screen
        showScreen('questionScreen');

        // Set question image
        const img = document.getElementById('questionImage');
        const placeholder = document.getElementById('imagePlaceholder');
        img.style.display = 'block';
        placeholder.classList.add('hidden');
        img.src = data.image_url;
        img.onerror = () => {
            img.style.display = 'none';
            placeholder.classList.remove('hidden');
        };

        // Set question text
        document.getElementById('questionNumBadge').textContent = `Q${data.question_number}`;
        document.getElementById('questionText').textContent = data.question;

        // Set options
        const letters = ['A', 'B', 'C', 'D'];
        data.options.forEach((opt, i) => {
            document.getElementById(`optText${i}`).textContent = opt;
            const btn = document.getElementById(`opt${i}`);
            btn.disabled = false;
            btn.classList.remove('correct', 'wrong', 'dimmed');
        });

        // Hide answered indicator
        document.getElementById('answeredIndicator').classList.add('hidden');

        // Start timer
        startPlayerTimer(data.time_limit || TIMER_DURATION);
    }
}

// ─── Timer ───────────────────────────────────────────────────────────────────

function startPlayerTimer(duration) {
    clearTimer();
    timeLeft = duration;
    updateTimerDisplay(timeLeft, duration);

    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimerDisplay(timeLeft, duration);

        if (timeLeft <= 0) {
            clearTimer();
            if (!hasAnswered) {
                // Time's up - no answer submitted
                disableAllOptions();
                showAnsweredIndicator(false, null);
            }
            // Notify server time is up
            socket.emit('time_up', { session_id: sessionId });
        }
    }, 1000);
}

function startHostTimer(duration) {
    clearTimer();
    timeLeft = duration;
    updateHostTimer(timeLeft, duration);

    timerInterval = setInterval(() => {
        timeLeft--;
        updateHostTimer(timeLeft, duration);

        if (timeLeft <= 0) {
            clearTimer();
            socket.emit('time_up', { session_id: sessionId });
        }
    }, 1000);
}

function updateTimerDisplay(current, total) {
    const bar = document.getElementById('timerBar');
    const display = document.getElementById('timerDisplay');
    if (!bar || !display) return;

    const pct = (current / total) * 100;
    bar.style.width = pct + '%';
    display.textContent = current;

    const isUrgent = current <= 5;
    bar.classList.toggle('urgent', isUrgent);
    display.classList.toggle('urgent', isUrgent);
}

function updateHostTimer(current, total) {
    const circle = document.getElementById('timerCircle');
    const numEl = document.getElementById('hostTimerNum');
    if (!circle || !numEl) return;

    const circumference = 283;
    const offset = circumference - (current / total) * circumference;
    circle.style.strokeDashoffset = offset;
    numEl.textContent = current;

    const isUrgent = current <= 5;
    circle.classList.toggle('urgent', isUrgent);
}

function clearTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// ─── Answer Submission ───────────────────────────────────────────────────────

function submitAnswer(optionIndex) {
    if (hasAnswered || isHost) return;

    hasAnswered = true;
    const timeTaken = Math.min(TIMER_DURATION, (Date.now() - questionStartTime) / 1000);
    const selectedAnswer = currentOptions[optionIndex];

    // Visual feedback - highlight selected
    disableAllOptions();
    document.getElementById(`opt${optionIndex}`).style.opacity = '1';
    document.getElementById(`opt${optionIndex}`).style.transform = 'scale(1.05)';

    // Show waiting indicator
    showAnsweredIndicator(null, selectedAnswer);

    // Send to server
    socket.emit('submit_answer', {
        session_id: sessionId,
        username: username,
        answer: selectedAnswer,
        time_taken: timeTaken
    });
}

function disableAllOptions() {
    for (let i = 0; i < 4; i++) {
        const btn = document.getElementById(`opt${i}`);
        if (btn) {
            btn.disabled = true;
            btn.classList.add('dimmed');
        }
    }
}

function showAnsweredIndicator(isCorrect, answer) {
    const indicator = document.getElementById('answeredIndicator');
    const icon = document.getElementById('answeredIcon');
    const text = document.getElementById('answeredText');

    indicator.classList.remove('hidden');

    if (isCorrect === null) {
        icon.textContent = '⏳';
        text.textContent = `Answered! Waiting for time to end...`;
    } else if (isCorrect) {
        icon.textContent = '✅';
        text.textContent = 'Correct! Great job!';
    } else {
        icon.textContent = '❌';
        text.textContent = 'Wrong answer!';
    }
}

// ─── Answer Result ───────────────────────────────────────────────────────────

function showAnswerResult(data) {
    clearTimer();

    // Highlight correct/wrong options
    for (let i = 0; i < currentOptions.length; i++) {
        const btn = document.getElementById(`opt${i}`);
        if (!btn) continue;
        btn.classList.remove('dimmed');
        if (currentOptions[i] === data.correct_answer) {
            btn.classList.add('correct');
            btn.classList.remove('wrong');
        } else if (hasAnswered && currentOptions[i] !== data.correct_answer) {
            btn.classList.add('wrong');
        }
    }

    // Update score
    currentScore = data.total_score;
    updateScoreDisplay();

    // Show result screen after brief delay
    setTimeout(() => {
        showScreen('resultScreen');

        const isCorrect = data.is_correct;
        document.getElementById('resultIcon').textContent = isCorrect ? '✅' : '❌';
        document.getElementById('resultTitle').textContent = isCorrect ? 'Correct! 🎉' : 'Wrong! 😢';
        document.getElementById('resultTitle').className = `result-title ${isCorrect ? 'correct-title' : 'wrong-title'}`;
        document.getElementById('correctAnswerDisplay').textContent = data.correct_answer;
        document.getElementById('pointsEarned').textContent = data.points_earned > 0 ? `+${data.points_earned} pts` : '0 pts';
        document.getElementById('totalScoreDisplay').textContent = data.total_score;
    }, 1500);
}

// ─── Leaderboard ─────────────────────────────────────────────────────────────

function showLeaderboard(data) {
    showScreen('leaderboardScreen');

    const list = document.getElementById('leaderboardList');
    list.innerHTML = '';

    const rankEmojis = ['🥇', '🥈', '🥉'];
    data.leaderboard.forEach((player, i) => {
        const row = document.createElement('div');
        row.className = `lb-row ${i === 0 ? 'lb-1st' : i === 1 ? 'lb-2nd' : i === 2 ? 'lb-3rd' : ''}`;
        row.style.animationDelay = `${i * 0.1}s`;
        row.innerHTML = `
            <span class="lb-rank">${i < 3 ? rankEmojis[i] : `#${i + 1}`}</span>
            <span class="lb-name">${escapeHtml(player.username)}</span>
            <span class="lb-score">${player.score} pts</span>
        `;
        list.appendChild(row);
    });

    const isLastQuestion = data.question_number >= data.total_questions;

    if (isHost) {
        // Show next question button for host
        document.getElementById('hostNextBtn').classList.remove('hidden');
        document.getElementById('nextQuestionCountdown').classList.add('hidden');

        if (isLastQuestion) {
            document.querySelector('#hostNextBtn button').textContent = '🏆 Show Final Results';
        }
    } else {
        // Auto-countdown for players
        document.getElementById('hostNextBtn').classList.add('hidden');
        document.getElementById('nextQuestionCountdown').classList.remove('hidden');

        let countdown = 5;
        document.getElementById('nextCountNum').textContent = countdown;
        const countInterval = setInterval(() => {
            countdown--;
            document.getElementById('nextCountNum').textContent = countdown;
            if (countdown <= 0) clearInterval(countInterval);
        }, 1000);
    }
}

function requestNextQuestion() {
    socket.emit('next_question', { session_id: sessionId });
    document.getElementById('hostNextBtn').classList.add('hidden');
}

// ─── Game Over ────────────────────────────────────────────────────────────────

function showGameOver(data) {
    showScreen('gameOverScreen');

    const list = document.getElementById('finalLeaderboard');
    list.innerHTML = '';

    const rankEmojis = ['🥇', '🥈', '🥉'];
    data.final_scores.forEach((player, i) => {
        const row = document.createElement('div');
        row.className = `lb-row ${i === 0 ? 'lb-1st' : i === 1 ? 'lb-2nd' : i === 2 ? 'lb-3rd' : ''}`;
        row.style.animationDelay = `${i * 0.1}s`;
        row.innerHTML = `
            <span class="lb-rank">${i < 3 ? rankEmojis[i] : `#${i + 1}`}</span>
            <span class="lb-name">${escapeHtml(player.username)}</span>
            <span class="lb-score">${player.score} pts</span>
        `;
        list.appendChild(row);
    });
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function updateScoreDisplay() {
    const el = document.getElementById('currentScore');
    if (el) el.textContent = currentScore;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
