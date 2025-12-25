import sys
from pathlib import Path

from rapidfuzz import fuzz
from PySide6.QtGui import QGuiApplication


ANSWERS_PATH = Path("answers.txt")
FUZZY_THRESHOLD = 80
MAX_QUERY_LEN = 2000


def norm(s: str) -> str:
    return " ".join(s.lower().split())


class ClipWatch:
    def __init__(self, app: QGuiApplication):
        if not ANSWERS_PATH.exists():
            print(f"❌ Не найден файл: {ANSWERS_PATH.resolve()}")
            sys.exit(1)

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]

        print(f"📄 Загружено строк: {len(self.answers)}")

        self.cb = app.clipboard()
        self.last = ""

        self.cb.dataChanged.connect(self.on_clipboard_changed)
        print("📋 Clipboard watcher запущен. Копируй текст (Ctrl+C).")

    def on_clipboard_changed(self):
        text = self.cb.text() or ""

        if text == self.last:
            return

        self.last = text

        print(f"🔹 Clipboard changed: {text[:80]!r}")

        if not text or len(text) > MAX_QUERY_LEN:
            print("⏭ пропуск (пусто или слишком длинно)")
            return

        q = norm(text)
        if not q:
            return

        # 1) Подстрока
        for line, ln in self.answers:
            if q in ln:
                print("✔ MATCH (substring):", line)
                self.cb.setText(line)
                self.last = line
                return

        # 2) Fuzzy
        best_score = 0
        best_line = None
        for line, ln in self.answers:
            score = fuzz.token_set_ratio(q, ln)
            if score > best_score:
                best_score = score
                best_line = line

        if best_score >= FUZZY_THRESHOLD:
            print(f"✔ MATCH (fuzzy {best_score}%):", best_line)
            self.cb.setText(best_line)
            self.last = best_line
        else:
            print(f"❌ no match (best {best_score}%)")


def main():
    print("▶ starting clipwatch")

    app = QGuiApplication(sys.argv)
    ClipWatch(app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
