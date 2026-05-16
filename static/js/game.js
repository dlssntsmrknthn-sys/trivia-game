/**
 * TriviaBlast - Client-side Game Logic
 * Server-driven: the server controls all timing via gevent.sleep()
 * Clients just display what the server sends.
 */

// ─── Sound Engine (Web Audio API — no external files needed) ─────────────────
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function getAudioCtx() {
    if (!audioCtx) audioCtx = new AudioCtx();
    return audioCtx;
}

function playTone(frequency, duration, type = 'sine', volume = 0.3, delay = 0) {
    try {
        const ctx = getAudioCtx();
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        oscillator.type = type;
        oscillator.frequency.setValueAtTime(frequency, ctx.currentTime + delay);
        gainNode.gain.setValueAtTime(volume, ctx.currentTime + delay);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + duration);
        oscillator.start(ctx.currentTime + delay);
        oscillator.stop(ctx.currentTime + delay + duration);
    } catch (e) { /* silently ignore audio errors */ }
}

function soundTick() {
    playTone(880, 0.08, 'square', 0.15);
}

function soundUrgentTick() {
    playTone(1100, 0.1, 'square', 0.25);
}

function soundCorrect() {
    playTone(523, 0.12, 'sine', 0.4);       // C5
    playTone(659, 0.12, 'sine', 0.4, 0.13); // E5
    playTone(784, 0.25, 'sine', 0.4, 0.26); // G5
}

function soundWrong() {
    playTone(300, 0.15, 'sawtooth', 0.3);
    playTone(200, 0.3, 'sawtooth', 0.3, 0.16);
}

function soundGameStart() {
    [261, 329, 392, 523].forEach((freq, i) => {
        playTone(freq, 0.2, 'sine', 0.35, i * 0.12);
    });
}

function soundGameOver() {
    [523, 659, 784, 1047].forEach((freq, i) => {
        playTone(freq, 0.3, 'sine', 0.4, i * 0.15);
    });
}

function soundCountdown() {
    playTone(440, 0.15, 'sine', 0.3);
}

let socket = null;
let sessionId = '';
let username = '';
let isHost = false;
let currentScore = 0;
let timerInterval = null;
let timeLeft = 10;
let currentOptions = [];
let hasAnswered = false;
let questionStartTime = null;
let lastAnswerResult = null; // stores the answer_result data for use in showQuestionResult

const TIMER_DURATION = 10;

function initGame(sid, uname, hostMode) {
    sessionId = sid;
    username = uname;
    isHost = hostMode;

    socket = io();
    setupSocketListeners();

    socket.on('connect', () => {
        console.log('Connected to game server');
        if (isHost) {
            socket.emit('host_join', { session_id: sessionId });
        } else {
            socket.emit('player_rejoin', { session_id: sessionId, username: username });
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
        soundGameStart();
        // Show waiting screen until first question arrives
        showScreen('waitingScreen');
    });

    socket.on('new_question', (data) => {
        receiveQuestion(data);
    });

    socket.on('answer_result', (data) => {
        lastAnswerResult = data; // store for use in showQuestionResult
        showAnswerResult(data);
    });

    socket.on('answer_count_update', (data) => {
        if (isHost) {
            document.getElementById('hostAnswered').textContent = data.answered;
            document.getElementById('hostTotal').textContent = data.total;
        }
    });

    socket.on('question_ended', (data) => {
        // Server says time is up — show correct answer briefly then server sends next question
        clearTimer();
        showQuestionResult(data);
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

    document.getElementById('questionProgress').textContent =
        `Question ${data.question_number} / ${data.total_questions}`;

    if (isHost) {
        showScreen('hostScreen');
        document.getElementById('hostQuestionText').textContent = data.question;
        document.getElementById('hostAnswered').textContent = '0';

        const preview = document.getElementById('hostOptionsPreview');
        const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12'];
        const letters = ['A', 'B', 'C', 'D'];
        preview.innerHTML = data.options.map((opt, i) =>
            `<div class="host-opt-preview" style="background:${colors[i]}">${letters[i]}. ${opt}</div>`
        ).join('');

        // Host shows a visual countdown but does NOT emit time_up
        startVisualTimer(data.time_limit || TIMER_DURATION);
    } else {
        showScreen('questionScreen');

        const img = document.getElementById('questionImage');
        const placeholder = document.getElementById('imagePlaceholder');
        img.style.display = 'block';
        placeholder.classList.add('hidden');
        img.src = data.image_url;
        img.onerror = () => {
            img.style.display = 'none';
            placeholder.classList.remove('hidden');
        };

        document.getElementById('questionNumBadge').textContent = `Q${data.question_number}`;
        document.getElementById('questionText').textContent = data.question;

        data.options.forEach((opt, i) => {
            document.getElementById(`optText${i}`).textContent = opt;
            const btn = document.getElementById(`opt${i}`);
            btn.disabled = false;
            btn.classList.remove('correct', 'wrong', 'dimmed');
        });

        document.getElementById('answeredIndicator').classList.add('hidden');

        startVisualTimer(data.time_limit || TIMER_DURATION);
    }
}

// ─── Timer (visual only — server controls actual timing) ─────────────────────

function startVisualTimer(duration) {
    clearTimer();
    timeLeft = duration;
    updateTimerDisplay(timeLeft, duration);

    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimerDisplay(timeLeft, duration);

        // Play tick sounds
        if (timeLeft > 0) {
            if (timeLeft <= 3) {
                soundUrgentTick();
            } else {
                soundTick();
            }
        }

        if (timeLeft <= 0) {
            clearTimer();
            if (!isHost && !hasAnswered) {
                disableAllOptions();
                showAnsweredIndicator(false, null);
            }
            // Server will send question_ended when time is up
        }
    }, 1000);
}

function updateTimerDisplay(current, total) {
    // Player timer bar
    const bar = document.getElementById('timerBar');
    const display = document.getElementById('timerDisplay');
    if (bar && display) {
        const pct = (current / total) * 100;
        bar.style.width = pct + '%';
        display.textContent = current;
        const isUrgent = current <= 3;
        bar.classList.toggle('urgent', isUrgent);
        display.classList.toggle('urgent', isUrgent);
    }

    // Host timer circle
    const circle = document.getElementById('timerCircle');
    const numEl = document.getElementById('hostTimerNum');
    if (circle && numEl) {
        const circumference = 283;
        const offset = circumference - (current / total) * circumference;
        circle.style.strokeDashoffset = offset;
        numEl.textContent = current;
        const isUrgent = current <= 3;
        circle.classList.toggle('urgent', isUrgent);
    }
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

    disableAllOptions();
    const selectedBtn = document.getElementById(`opt${optionIndex}`);
    if (selectedBtn) {
        selectedBtn.style.opacity = '1';
        selectedBtn.style.transform = 'scale(1.05)';
    }

    showAnsweredIndicator(null, selectedAnswer);

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
        text.textContent = 'Answered! Waiting for results...';
    } else if (isCorrect) {
        icon.textContent = '✅';
        text.textContent = 'Correct! Great job!';
    } else {
        icon.textContent = '❌';
        text.textContent = 'Wrong answer!';
    }
}

// ─── Answer Result (from server after submitting) ────────────────────────────

function showAnswerResult(data) {
    // Highlight correct/wrong options
    for (let i = 0; i < currentOptions.length; i++) {
        const btn = document.getElementById(`opt${i}`);
        if (!btn) continue;
        btn.classList.remove('dimmed');
        if (currentOptions[i] === data.correct_answer) {
            btn.classList.add('correct');
        } else {
            btn.classList.add('wrong');
        }
    }

    currentScore = data.total_score;
    updateScoreDisplay();

    // Play correct/wrong sound
    if (data.is_correct) {
        soundCorrect();
    } else {
        soundWrong();
    }

    // Update answered indicator
    const indicator = document.getElementById('answeredIndicator');
    const icon = document.getElementById('answeredIcon');
    const text = document.getElementById('answeredText');
    if (indicator) {
        indicator.classList.remove('hidden');
        icon.textContent = data.is_correct ? '✅' : '❌';
        text.textContent = data.is_correct
            ? `Correct! +${data.points_earned} pts`
            : `Wrong! Correct: ${data.correct_answer}`;
    }
}

// ─── Question Ended (server-driven, shows result then auto-advances) ──────────

function showQuestionResult(data) {
    // Show the result screen with correct answer and leaderboard
    // Server will auto-send next question after RESULT_TIME seconds

    if (isHost) {
        // Host sees leaderboard
        showScreen('leaderboardScreen');
        renderLeaderboard(data.leaderboard, data.question_number, data.total_questions);

        // Hide next button — server auto-advances
        const hostNextBtn = document.getElementById('hostNextBtn');
        if (hostNextBtn) hostNextBtn.classList.add('hidden');

        const countdown = document.getElementById('nextQuestionCountdown');
        if (countdown) countdown.classList.remove('hidden');
        startCountdownDisplay(3);
    } else {
        // Players see result screen with correct answer + their score
        showScreen('resultScreen');

        const correctAnswer = data.correct_answer;
        document.getElementById('correctAnswerDisplay').textContent = correctAnswer;

        // Use stored answer_result data if available
        if (lastAnswerResult) {
            const resultIcon = document.getElementById('resultIcon');
            const resultTitle = document.getElementById('resultTitle');
            const pointsEarned = document.getElementById('pointsEarned');
            const totalScoreDisplay = document.getElementById('totalScoreDisplay');

            if (resultIcon) resultIcon.textContent = lastAnswerResult.is_correct ? '✅' : '❌';
            if (resultTitle) resultTitle.textContent = lastAnswerResult.is_correct ? 'Correct!' : 'Wrong!';
            if (pointsEarned) pointsEarned.textContent = lastAnswerResult.points_earned > 0
                ? `+${lastAnswerResult.points_earned} pts`
                : '0 pts';
            if (totalScoreDisplay) totalScoreDisplay.textContent = lastAnswerResult.total_score;
        } else {
            // Player didn't answer (time ran out)
            const resultIcon = document.getElementById('resultIcon');
            const resultTitle = document.getElementById('resultTitle');
            const pointsEarned = document.getElementById('pointsEarned');
            const totalScoreDisplay = document.getElementById('totalScoreDisplay');

            if (resultIcon) resultIcon.textContent = '⏰';
            if (resultTitle) resultTitle.textContent = 'Time\'s Up!';
            if (pointsEarned) pointsEarned.textContent = '0 pts';
            if (totalScoreDisplay) totalScoreDisplay.textContent = currentScore;
        }

        // Reset lastAnswerResult for next question
        lastAnswerResult = null;

        // Show leaderboard after 1.5 seconds
        setTimeout(() => {
            showScreen('leaderboardScreen');
            renderLeaderboard(data.leaderboard, data.question_number, data.total_questions);

            const hostNextBtn = document.getElementById('hostNextBtn');
            if (hostNextBtn) hostNextBtn.classList.add('hidden');

            const countdown = document.getElementById('nextQuestionCountdown');
            if (countdown) countdown.classList.remove('hidden');
            startCountdownDisplay(2);
        }, 1500);
    }
}

function renderLeaderboard(leaderboard, questionNum, totalQuestions) {
    const list = document.getElementById('leaderboardList');
    if (!list) return;
    list.innerHTML = '';

    const rankEmojis = ['🥇', '🥈', '🥉'];
    leaderboard.forEach((player, i) => {
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

function startCountdownDisplay(seconds) {
    const numEl = document.getElementById('nextCountNum');
    if (!numEl) return;
    numEl.textContent = seconds;
    const interval = setInterval(() => {
        seconds--;
        numEl.textContent = seconds;
        if (seconds <= 0) clearInterval(interval);
    }, 1000);
}

// ─── Game Over ────────────────────────────────────────────────────────────────

function showGameOver(data) {
    clearTimer();
    soundGameOver();
    showScreen('gameOverScreen');

    const list = document.getElementById('finalLeaderboard');
    if (!list) return;
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
