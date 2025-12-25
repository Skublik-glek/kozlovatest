#!/usr/bin/env python3
import sys
import time
from pathlib import Path

from rapidfuzz import fuzz
from PySide6.QtCore import QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QTextEdit, QPushButton, QHBoxLayout
)

# answers.txt будет лежать рядом с exe/скриптом
ANSWERS_PATH = Path("answers.txt")

FUZZY_THRESHOLD = 80
POLL_MS = 200
MAX_QUERY_LEN = 2000


def norm(s: str) -> str:
    return " ".join(s.lower().split())


class AnswerFinder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Answer Finder")
        self.resize(720, 420)

        self.status = QLabel("Запуск…")
        self.clip_preview = QLabel("Clipboard: (пусто)")
        self.clip_preview.setWordWrap(True)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Здесь появится найденная строка из answers.txt")

        self.btn_reload = QPushButton("Перезагрузить answers.txt")
        self.btn_clear = QPushButton("Очистить вывод")

        btns = QHBoxLayout()
        btns.addWidget(self.btn_reload)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.clip_preview)
        layout.addLayout(btns)
        layout.addWidget(self.output)

        self.btn_reload.clicked.connect(self.load_answers)
        self.btn_clear.clicked.connect(lambda: self.output.setPlainText(""))

        self.cb = QApplication.clipboard()

        self.answers = []
        self.last_seen = ""
        self.last_external = ""
        self.last_external_time = 0.0

        self.load_answers()

        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def load_answers(self):
        if not ANSWERS_PATH.exists():
            self.status.setText(f"❌ answers.txt не найден: {ANSWERS_PATH.resolve()}")
            self.answers = []
            return

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]
        self.status.setText(f"🟢 Активно | Строк в answers.txt: {len(self.answers)} | poll={POLL_MS}ms")

    def read_clipboard(self) -> str:
        # На Windows это просто работает; на Linux/Wayland тоже нормально для чтения.
        _ = self.cb.mimeData(QClipboard.Clipboard)
        return self.cb.text(QClipboard.Clipboard) or ""

    def tick(self):
        text = self.read_clipboard()

        if text == self.last_seen:
            return
        self.last_seen = text

        preview = (text[:180].replace("\n", " ") + ("…" if len(text) > 180 else "")) if text else "(пусто)"
        self.clip_preview.setText(f"Clipboard: {preview}")

        if not text or len(text) > MAX_QUERY_LEN or not self.answers:
            return

        now = time.monotonic()
        if text == self.last_external and (now - self.last_external_time) < 0.25:
            return
        self.last_external = text
        self.last_external_time = now

        q = norm(text)
        if not q:
            return

        # 1) substring (case-insensitive)
        for line, ln in self.answers:
            if q in ln:
                self.show_match(line, why="substring")
                return

        # 2) fuzzy
        best_score = 0
        best_line = None
        for line, ln in self.answers:
            score = fuzz.token_set_ratio(q, ln)
            if score > best_score:
                best_score = score
                best_line = line

        if best_line and best_score >= FUZZY_THRESHOLD:
            self.show_match(best_line, why=f"fuzzy {best_score}%")
        else:
            self.status.setText(
                f"🟢 Активно | Строк: {len(self.answers)} | нет совпадений (best {best_score}%)"
            )

    def show_match(self, line: str, why: str):
        self.status.setText(f"🟢 MATCH: {why}")
        self.output.setPlainText(line)


def main():
    app = QApplication(sys.argv)
    w = AnswerFinder()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
