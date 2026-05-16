"""
Google Sheets Sync for TriviaBlast
====================================
Reads questions from the "Questions" tab and logs scores to the "Log" tab.

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


def _get_credentials():
    """Load Google credentials from env var or credentials.json file."""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if creds_json:
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError as e:
            print(f"[Sheets] Error parsing GOOGLE_CREDENTIALS env var: {e}")
            return None

    creds_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Sheets] Error reading credentials.json: {e}")
            return None

    print("[Sheets] No credentials found.")
    return None


def _get_client():
    """Create a fresh gspread client each time (avoids stale token issues)."""
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
        client = gspread.authorize(creds)
        return client

    except ImportError:
        print("[Sheets] gspread not installed.")
        return None
    except Exception as e:
        print(f"[Sheets] Failed to initialize client: {e}")
        return None


def _get_spreadsheet():
    """Get a fresh spreadsheet connection."""
    client = _get_client()
    if client is None:
        return None
    try:
        return client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print(f"[Sheets] Failed to open spreadsheet: {e}")
        return None


def load_questions_from_sheet():
    """
    Load ALL questions from the 'Questions' tab.
    Returns a list of question dicts, or None if unavailable.
    """
    ss = _get_spreadsheet()
    if ss is None:
        return None

    try:
        ws = ss.worksheet(QUESTIONS_SHEET)
        all_values = ws.get_all_values()

        if len(all_values) < 2:
            print("[Sheets] Questions sheet is empty or has only headers")
            return None

        questions = []
        for i, row in enumerate(all_values[1:], start=1):
            while len(row) < 7:
                row.append('')

            genre    = row[0].strip()
            question = row[1].strip()
            opt_a    = row[2].strip()
            opt_b    = row[3].strip()
            opt_c    = row[4].strip()
            opt_d    = row[5].strip()
            answer   = row[6].strip()

            if not question or not answer:
                continue

            keyword = genre if genre else question[:30]

            # Normalize answer: strip "B) " prefix if present
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


def log_session_scores(session_id, final_scores):
    """
    Write final scores for a session to the Log sheet.
    Uses a fresh connection each time to avoid stale token issues.
    """
    print(f"[Sheets] Attempting to log {len(final_scores)} scores for session {session_id}...")

    ss = _get_spreadsheet()
    if ss is None:
        print(f"[Sheets] ❌ Cannot log scores — no connection. Session: {session_id}")
        return False

    try:
        # Get or create Log worksheet
        try:
            ws = ss.worksheet(LOG_SHEET)
            print(f"[Sheets] Found '{LOG_SHEET}' worksheet")
        except Exception as e:
            print(f"[Sheets] '{LOG_SHEET}' tab not found, creating it... ({e})")
            ws = ss.add_worksheet(title=LOG_SHEET, rows=1000, cols=10)
            ws.update('A1:E1', [['Session ID', 'Username', 'Score', 'Rank', 'Logged At']])
            print(f"[Sheets] Created '{LOG_SHEET}' tab with headers")

        # Check/set headers
        try:
            existing_headers = ws.row_values(1)
            expected = ['Session ID', 'Username', 'Score', 'Rank', 'Logged At']
            if existing_headers[:5] != expected:
                ws.update('A1:E1', [expected])
                print("[Sheets] Updated headers in Log tab")
        except Exception as e:
            print(f"[Sheets] Warning: could not check headers: {e}")

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
            print(f"[Sheets] ✅ Successfully logged {len(rows)} scores for session {session_id}")
            return True
        else:
            print(f"[Sheets] No scores to log for session {session_id}")
            return False

    except Exception as e:
        print(f"[Sheets] ❌ Error logging scores: {e}")
        import traceback
        traceback.print_exc()
        return False


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
