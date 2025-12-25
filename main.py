import sys
from pathlib import Path

from rapidfuzz import fuzz
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication


ANSWERS_PATH = Path("answers.txt")
FUZZY_THRESHOLD = 80
MAX_QUERY_LEN = 2000
POLL_MS = 250  # как часто проверять буфер


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
        self.last_seen = ""
        self.last_set_by_us = ""

        # Таймер вместо dataChanged (на Wayland часто надёжнее)
        self.timer = QTimer()
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        print(f"📋 Watcher запущен (poll {POLL_MS}ms). Копируй текст. Ctrl+C чтобы выйти.")

    def tick(self):
        text = self.cb.text() or ""

        if text == self.last_seen:
            return

        self.last_seen = text
        print(f"🔹 Clipboard: {text[:80]!r}")

        # (опционально) если боишься вечной самоподстановки — можно пропускать
        # собственную последнюю установку, но ты говорил что это не страшно.
        # Если всё же хочешь — раскомментируй:
        # if text == self.last_set_by_us:
        #     return

        if not text or len(text) > MAX_QUERY_LEN:
            print("⏭ пропуск (пусто/слишком длинно)")
            return

        q = norm(text)
        if not q:
            return

        # 1) Подстрока без регистра
        for line, ln in self.answers:
            if q in ln:
                print("✔ MATCH (substring):", line)
                self.cb.setText(line)
                self.last_set_by_us = line
                self.last_seen = line
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
            self.last_set_by_us = best_line
            self.last_seen = best_line
        else:
            print(f"❌ no match (best {best_score}%)")


def main():
    print("▶ starting clipwatch (Qt polling mode)")
    app = QGuiApplication(sys.argv)
    ClipWatch(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
