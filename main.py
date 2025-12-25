#!/usr/bin/env python3
import sys
import time
from pathlib import Path
from rapidfuzz import fuzz

from PySide6.QtCore import QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

ANSWERS_PATH = Path("answers.txt")

FUZZY_THRESHOLD = 80
POLL_MS = 200

# подавление реакции на собственную запись
SELF_SUPPRESS_SEC = 0.7

# задержка записи в буфер, чтобы победить “гонку” (источник копирования перезаписывает)
SET_DELAY_MS = 120

# если хочешь разрешать повтор одного и того же запроса — поставь, например, 2.0 сек
REPEAT_COOLDOWN_SEC = 0.0


def norm(s: str) -> str:
    return " ".join(s.lower().split())


class ClipWatch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipboard Watcher")
        self.setFixedSize(390, 140)
        self.label = QLabel("Запуск…")
        QVBoxLayout(self).addWidget(self.label)

        if not ANSWERS_PATH.exists():
            self.label.setText(f"❌ answers.txt не найден:\n{ANSWERS_PATH.resolve()}")
            self.answers = []
            return

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]

        self.cb = QApplication.clipboard()

        # последнее реально увиденное значение буфера (любое)
        self.last_seen_clip = ""

        # последнее, что записали мы
        self.last_set_by_us = ""

        # до какого времени игнорируем свои “эхо”-изменения
        self.suppress_until = 0.0

        # если во время подавления пришёл внешний текст — сохраняем сюда
        self.pending_external = None

        # анти-спам одинаковых копий
        self.last_external = ""
        self.last_external_time = 0.0

        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        self.label.setText(
            f"🟢 Активно\n"
            f"Строк: {len(self.answers)}\n"
            f"Можно свернуть окно. Жду копирования…"
        )
        print("▶ clipwatch started. Copy something…", flush=True)

    def read_clipboard(self) -> str:
        _ = self.cb.mimeData(QClipboard.Clipboard)  # форс запроса (Wayland)
        return self.cb.text(QClipboard.Clipboard) or ""

    def tick(self):
        now = time.monotonic()
        text = self.read_clipboard()

        # 1) если буфер вообще не менялся — выходим
        if text == self.last_seen_clip:
            # но если подавление закончилось и есть pending — обработаем
            if now >= self.suppress_until and self.pending_external:
                pending = self.pending_external
                self.pending_external = None
                self.process_external(pending, now, source="pending")
            return

        # буфер изменился
        self.last_seen_clip = text

        # 2) если это наш же ответ — игнор
        if text == self.last_set_by_us:
            return

        # 3) если мы в режиме подавления — НЕ теряем событие, а кладём в pending
        if now < self.suppress_until:
            self.pending_external = text
            return

        # 4) иначе обрабатываем как внешнее копирование
        self.process_external(text, now, source="poll")

    def process_external(self, text: str, now: float, source: str):
        if not text:
            return

        # опционально: игнорировать одинаковую копию подряд (или разрешить через cooldown)
        if text == self.last_external and (now - self.last_external_time) < REPEAT_COOLDOWN_SEC:
            return

        self.last_external = text
        self.last_external_time = now

        preview = text[:90].replace("\n", " ")
        print(f"[{source}] external: {preview!r}", flush=True)

        q = norm(text)
        if not q:
            return

        # 1) substring match (case-insensitive)
        for line, ln in self.answers:
            if q in ln:
                self.set_answer(line, why="substring")
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
            self.set_answer(best_line, why=f"fuzzy {best_score}%")
        else:
            print(f"❌ no match (best {best_score}%)", flush=True)

    def set_answer(self, line: str, why: str):
        print(f"✔ MATCH ({why}): {line}", flush=True)

        # подавляем “эхо” от своей записи
        self.last_set_by_us = line
        self.suppress_until = time.monotonic() + SELF_SUPPRESS_SEC

        # пока мы подавляем, внешний текст может прийти — пусть сохранится в pending
        self.pending_external = None

        self.label.setText(
            f"🟢 Активно\n"
            f"Последний матч: {why}\n"
            f"Пишу ответ в буфер…"
        )

        def do_set():
            self.cb.setText(line, QClipboard.Clipboard)
            QApplication.processEvents()

            # после записи обновим last_seen_clip, чтобы polling не счёл это “новым внешним”
            self.last_seen_clip = self.read_clipboard()

            self.label.setText(
                f"🟢 Активно\n"
                f"Последний матч: {why}\n"
                f"✅ Ответ в буфере"
            )

        # задержка, чтобы не проиграть источнику копирования
        QTimer.singleShot(SET_DELAY_MS, do_set)


def main():
    app = QApplication(sys.argv)
    w = ClipWatch()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
