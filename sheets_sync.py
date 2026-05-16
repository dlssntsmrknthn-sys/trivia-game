"""
Google Sheets Sync for TriviaBlast
====================================
Reads questions from the "Questions" tab and logs scores to the "Log" tab.

Spreadsheet: https://docs.google.com/spreadsheets/d/1dexaAuVyMPB676q28CeP9sh52J3Vk0SSleWNAxgYj3U/

Questions tab columns:
  A: Genre (used as image keyword)
  B: Question
  C: Option A
  D: Option B
  E: Option C
  F: Option D
  G: Correct Answer

Log tab columns (auto-written):
  A: Session ID | B: Username | C: Score | D: Rank | E: Logged At
"""

import os
import json
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────
SPREADSHEET_ID = "1b7AjeBtaTifFDBm-iwVUJL3fRp1VGsHMWpwAbJiKeH8"
QUESTIONS_SHEET = "Questions"
LOG_SHEET = "Log"
# ─────────────────────────────────────────────────────────────────────────────

_client = None
_spreadsheet = None


def _get_credentials():
    """
    Load Google credentials from environment variable GOOGLE_CREDENTIALS (JSON string)
    or fall back to credentials.json file in the project directory.
    """
    # Try environment variable first (used in Railway/cloud deployment)
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if creds_json:
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError as e:
            print(f"[Sheets] Error parsing GOOGLE_CREDENTIALS env var: {e}")
            return None

    # Fall back to credentials.json file
    creds_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Sheets] Error reading credentials.json: {e}")
            return None

    print("[Sheets] No credentials found. Set GOOGLE_CREDENTIALS env var or add credentials.json")
    return None


def _get_client():
    """Initialize and return the gspread client."""
    global _client
    if _client is not None:
        return _client

    creds_data = _get_credentials()
    if creds_data is None:
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
        _client = gspread.authorize(creds)
        print("[Sheets] ✅ Google Sheets client initialized")
        return _client

    except ImportError:
        print("[Sheets] gspread not installed. Run: uv add gspread google-auth")
        return None
    except Exception as e:
        print(f"[Sheets] Failed to initialize client: {e}")
        return None


def _get_spreadsheet():
    """Get the spreadsheet object."""
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet

    client = _get_client()
    if client is None:
        return None

    try:
        _spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return _spreadsheet
    except Exception as e:
        print(f"[Sheets] Failed to open spreadsheet: {e}")
        return None


def load_questions_from_sheet():
    """
    Load questions from the 'Questions' tab.
    
    Column mapping:
      A=Genre (keyword), B=Question, C=Option A, D=Option B,
      E=Option C, F=Option D, G=Correct Answer

    Returns a list of question dicts, or None if unavailable.
    """
    ss = _get_spreadsheet()
    if ss is None:
        return None

    try:
        ws = ss.worksheet(QUESTIONS_SHEET)
        # Get all values (skip header row 1)
        all_values = ws.get_all_values()

        if len(all_values) < 2:
            print("[Sheets] Questions sheet is empty or has only headers")
            return None

        questions = []
        # Row 0 is header, start from row 1
        for i, row in enumerate(all_values[1:], start=1):
            # Pad row to at least 7 columns
            while len(row) < 7:
                row.append('')

            genre   = row[0].strip()   # Column A: Genre
            question = row[1].strip()  # Column B: Question
            opt_a   = row[2].strip()   # Column C: Option A
            opt_b   = row[3].strip()   # Column D: Option B
            opt_c   = row[4].strip()   # Column E: Option C
            opt_d   = row[5].strip()   # Column F: Option D
            answer  = row[6].strip()   # Column G: Correct Answer

            # Skip empty rows
            if not question or not answer:
                continue

            # Use genre as image keyword, fall back to first 30 chars of question
            keyword = genre if genre else question[:30]

            # Normalize answer: strip "B) " prefix if present
            # so answer matches the plain option text
            def strip_prefix(s):
                s = s.strip()
                if len(s) > 2 and s[1] == ')':
                    return s[2:].strip()
                return s

            clean_answer = strip_prefix(answer)

            questions.append({
                'id': i,
                'question': question,
                'options': [opt_a, opt_b, opt_c, opt_d],
                'answer': clean_answer,
                'keyword': keyword,
                'genre': genre
            })

        print(f"[Sheets] ✅ Loaded {len(questions)} questions from Google Sheets")
        return questions if questions else None

    except Exception as e:
        print(f"[Sheets] Error loading questions: {e}")
        return None


def ensure_log_headers():
    """Make sure the Log sheet has the correct headers."""
    ss = _get_spreadsheet()
    if ss is None:
        return False

    try:
        try:
            ws = ss.worksheet(LOG_SHEET)
        except Exception:
            ws = ss.add_worksheet(title=LOG_SHEET, rows=1000, cols=10)

        existing = ws.row_values(1)
        headers = ['Session ID', 'Username', 'Score', 'Rank', 'Logged At']
        if existing[:5] != headers:
            ws.update('A1:E1', [headers])
            print(f"[Sheets] Headers set in '{LOG_SHEET}' tab")
        return True

    except Exception as e:
        print(f"[Sheets] Error ensuring log headers: {e}")
        return False


def log_session_scores(session_id, final_scores):
    """
    Write final scores for a session to the Log sheet.

    Args:
        session_id (str): The game session ID
        final_scores (list): List of dicts with 'username' and 'score',
                             sorted by score descending
    """
    ss = _get_spreadsheet()
    if ss is None:
        print(f"[Sheets] Cannot log scores — no connection. Session: {session_id}")
        return

    try:
        try:
            ws = ss.worksheet(LOG_SHEET)
        except Exception:
            ws = ss.add_worksheet(title=LOG_SHEET, rows=1000, cols=10)
            ws.update('A1:E1', [['Session ID', 'Username', 'Score', 'Rank', 'Logged At']])

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows = []
        for i, player in enumerate(final_scores):
            rows.append([
                session_id,
                player.get('username', ''),
                player.get('score', 0),
                i + 1,
                now
            ])

        if rows:
            ws.append_rows(rows, value_input_option='USER_ENTERED')
            print(f"[Sheets] ✅ Logged {len(rows)} scores for session {session_id}")

    except Exception as e:
        print(f"[Sheets] Error logging scores: {e}")


if __name__ == '__main__':
    print("Testing Google Sheets connection...")
    qs = load_questions_from_sheet()
    if qs:
        print(f"✅ Successfully loaded {len(qs)} questions!")
        print(f"   Sample: {qs[0]['question']}")
        print(f"   Options: {qs[0]['options']}")
        print(f"   Answer: {qs[0]['answer']}")
    else:
        print("❌ Could not load questions. Check credentials and sheet access.")
