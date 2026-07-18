import re

def fix_mojibake(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read()
    # â€" (mojibake for —) in UTF-8: C3 A2 E2 82 AC E2 80 9D
    bad = b'\xc3\xa2\xe2\x82\xac\xe2\x80\x9d'
    em_dash = '\u2014'.encode('utf-8')
    count = raw.count(bad)
    if count:
        fixed = raw.replace(bad, em_dash)
        with open(filepath, 'wb') as f:
            f.write(fixed)
        print(f"Fixed {count} mojibake sequences in {filepath}")
    else:
        print(f"No mojibake found in {filepath}")

fix_mojibake('backend/routers/chat.py')
fix_mojibake('agent/ui/tui.py')
