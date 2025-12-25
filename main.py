import time
from pathlib import Path
import pyperclip
from rapidfuzz import fuzz

ANSWERS_FILE = Path("answers.txt")
CHECK_INTERVAL = 0.25  # сек

# Fuzzy-настройки
FUZZY_THRESHOLD = 80   # 0..100 (подними до 85-90, если много ложных)
MAX_QUERY_LEN = 2000   # защита от простыней

def norm(s: str) -> str:
    return " ".join(s.strip().split()).lower()

if not ANSWERS_FILE.exists():
    raise FileNotFoundError("Файл answers.txt не найден")

answers_raw = ANSWERS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
answers = [(line, norm(line)) for line in answers_raw if line.strip()]

last_clipboard = ""

print("📋 Clipboard watcher (case-insensitive + fuzzy). Ctrl+C чтобы выйти.")

while True:
    try:
        clip = pyperclip.paste()

        if clip == last_clipboard:
            time.sleep(CHECK_INTERVAL)
            continue

        last_clipboard = clip

        if not clip or len(clip) > MAX_QUERY_LEN:
            continue

        q = norm(clip)
        if not q:
            continue

        # 1) Быстрый подстрочный поиск (без регистра)
        found_line = None
        for line, line_norm in answers:
            if q in line_norm:
                found_line = line
                break

        # 2) Если не нашли — fuzzy
        if found_line is None:
            best_score = -1
            best_line = None

            # token_set_ratio хорошо переживает перестановки слов/лишние слова
            for line, line_norm in answers:
                score = fuzz.token_set_ratio(q, line_norm)
                if score > best_score:
                    best_score = score
                    best_line = line

            if best_score >= FUZZY_THRESHOLD:
                found_line = best_line

        # Если нашли — печать + в буфер
        if found_line:
            print("✔ MATCH:", found_line)
            pyperclip.copy(found_line)
            last_clipboard = found_line  # чтобы не дёргалось по кругу

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем")
        break
