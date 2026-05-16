import sheets_sync

print("Testing Google Sheets connection...")
qs = sheets_sync.load_questions_from_sheet()
if qs:
    print(f"SUCCESS: Loaded {len(qs)} questions")
    print(f"First Q: {qs[0]['question']}")
    print(f"Options: {qs[0]['options']}")
    print(f"Answer: {qs[0]['answer']}")
    print(f"Genre: {qs[0]['genre']}")
else:
    print("FAILED: Could not load questions")
