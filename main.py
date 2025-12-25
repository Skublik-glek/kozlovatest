import sys
from pathlib import Path
from rapidfuzz import fuzz

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
)

ANSWERS_PATH = Path("answers.txt")
FUZZY_THRESHOLD = 80
POLL_MS = 250


def norm(s: str) -> str:
    return " ".join(s.lower().split())


class ClipWatch(QWidget):
    def __init__(self):
        super().__init__()

        # ---------- UI ----------
        self.setWindowTitle("Clipboard Watcher")
        self.setFixedSize(260, 90)

        self.label = QLabel("🟢 Активно\nСверните окно — логика работает")
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # ---------- Data ----------
        if not ANSWERS_PATH.exists():
            self.label.setText("❌ answers.txt не найден")
            return

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]

        self.cb = QApplication.clipboard()
        self.last_seen = ""

        # ---------- Polling ----------
        self.timer = QTimer()
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        print("Clipboard watcher started")

    def tick(self):
        text = self.cb.text() or ""
        if text == self.last_seen:
            return

        self.last_seen = text
        print("Clipboard:", text[:60])

        q = norm(text)
        if not q:
            return

        # 1) substring
        for line, ln in self.answers:
            if q in ln:
                self.cb.setText(line)
                self.last_seen = line
                print("MATCH:", line)
                return

        # 2) fuzzy
        best_score = 0
        best_line = None
        for line, ln in self.answers:
            score = fuzz.token_set_ratio(q, ln)
            if score > best_score:
                best_score = score
                best_line = line

        if best_score >= FUZZY_THRESHOLD:
            self.cb.setText(best_line)
            self.last_seen = best_line
            print(f"FUZZY {best_score}%:", best_line)


def main():
    app = QApplication(sys.argv)
    w = ClipWatch()
    w.show()          # ← КЛЮЧЕВО
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
