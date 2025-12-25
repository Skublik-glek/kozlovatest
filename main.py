import sys
from pathlib import Path
from rapidfuzz import fuzz

from PySide6.QtCore import QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

ANSWERS_PATH = Path("answers.txt")
FUZZY_THRESHOLD = 80
POLL_MS = 250

def norm(s: str) -> str:
    return " ".join(s.lower().split())

class ClipWatch(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Clipboard Watcher")
        self.setFixedSize(320, 110)

        self.label = QLabel("🟢 Активно\nМожно свернуть, но не закрывать.\nЖду копирования…")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        if not ANSWERS_PATH.exists():
            self.label.setText(f"❌ answers.txt не найден: {ANSWERS_PATH.resolve()}")
            self.answers = []
            return

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]
        self.label.setText(f"🟢 Активно\nСтрок в answers.txt: {len(self.answers)}\nЖду копирования…")

        self.cb = QApplication.clipboard()
        self.last_seen = ""

        # Важно для Wayland: слушаем changed(mode)
        self.cb.changed.connect(self.on_clipboard_changed)

        # И дополнительно поллим (на случай, если сигнал не придёт)
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll_clipboard)
        self.timer.start()

        print("Started. Copy something…", flush=True)

    def read_clipboard(self) -> str:
        # Форсим запрос данных у Wayland:
        _ = self.cb.mimeData(QClipboard.Clipboard)
        return self.cb.text(QClipboard.Clipboard) or ""

    def poll_clipboard(self):
        self.process_text(self.read_clipboard(), source="poll")

    def on_clipboard_changed(self, mode: QClipboard.Mode):
        if mode != QClipboard.Clipboard:
            return
        self.process_text(self.read_clipboard(), source="signal")

    def process_text(self, text: str, source: str):
        if not text or text == self.last_seen:
            return

        self.last_seen = text
        print(f"[{source}] clipboard: {text[:80]!r}", flush=True)

        q = norm(text)
        if not q:
            return

        # 1) Подстрока
        for line, ln in self.answers:
            if q in ln:
                self.set_answer(line, "substring")
                return

        # 2) Fuzzy
        best_score = 0
        best_line = None
        for line, ln in self.answers:
            score = fuzz.token_set_ratio(q, ln)
            if score > best_score:
                best_score = score
                best_line = line

        if best_score >= FUZZY_THRESHOLD and best_line:
            self.set_answer(best_line, f"fuzzy {best_score}%")

    def set_answer(self, line: str, why: str):
        print(f"✔ MATCH ({why}): {line}", flush=True)
        self.cb.setText(line, QClipboard.Clipboard)
        self.last_seen = line
        self.label.setText(f"🟢 Активно\nПоследний матч: {why}\n(строка скопирована в буфер)")

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    w = ClipWatch()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
