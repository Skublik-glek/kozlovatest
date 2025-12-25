import sys
from pathlib import Path
from rapidfuzz import fuzz

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

ANSWERS_PATH = Path("answers.txt")
FUZZY_THRESHOLD = 80
MAX_QUERY_LEN = 2000
POLL_MS = 250

def norm(s: str) -> str:
    return " ".join(s.lower().split())

class ClipWatch:
    def __init__(self, app: QApplication):
        if not ANSWERS_PATH.exists():
            print(f"❌ Не найден файл: {ANSWERS_PATH.resolve()}")
            sys.exit(1)

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]
        print(f"📄 Загружено строк: {len(self.answers)}")

        # Невидимый виджет — критично для Wayland/Qt
        self.w = QWidget()
        self.w.setWindowTitle("clipwatch-hidden")
        self.w.hide()

        self.cb = app.clipboard()
        self.last_seen = None

        # Heartbeat: раз в 1 сек печатаем точку, чтобы видеть что живой
        self.hb = QTimer()
        self.hb.setInterval(1000)
        self.hb.timeout.connect(lambda: print("·", end="", flush=True))
        self.hb.start()

        # Polling clipboard
        self.timer = QTimer()
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        print(f"\n📋 Watcher запущен (poll {POLL_MS}ms). Копируй текст. Ctrl+C чтобы выйти.", flush=True)

    def tick(self):
        text = self.cb.text() or ""

        # Печатаем только когда изменилось
        if text == self.last_seen:
            return
        self.last_seen = text

        print(f"\n🔹 Clipboard changed: {text[:80]!r}", flush=True)

        if not text or len(text) > MAX_QUERY_LEN:
            print("⏭ пропуск (пусто/слишком длинно)", flush=True)
            return

        q = norm(text)
        if not q:
            return

        # 1) Подстрока
        for line, ln in self.answers:
            if q in ln:
                print("✔ MATCH (substring):", line, flush=True)
                self.cb.setText(line)
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
            print(f"✔ MATCH (fuzzy {best_score}%):", best_line, flush=True)
            self.cb.setText(best_line)
            self.last_seen = best_line
        else:
            print(f"❌ no match (best {best_score}%)", flush=True)

def main():
    print("▶ starting clipwatch (Qt hidden-widget mode)", flush=True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    ClipWatch(app)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
