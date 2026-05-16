@echo off
echo ================================================
echo   TriviaBlast - Multiplayer Trivia Game
echo ================================================
echo.
echo Starting server...
cd /d "%~dp0"
uv run python app.py
pause
