import bms_parser
import os

file_path = r"d:\계산기\패턴 모음2(GCS)\GCS BOOM\Altale (by 削除)\Altale_10GB.bms"

print(f"Testing parser on: {file_path}")
if not os.path.exists(file_path):
    print("File does not exist!")
else:
    try:
        parser = bms_parser.BMSParser(file_path)
        print("Parser initialized.")
        notes = parser.parse()
        print(f"Parsed {len(notes)} notes.")
        print(f"Header: {parser.header}")
    except Exception as e:
        print(f"Parser failed: {e}")
        import traceback
        traceback.print_exc()
