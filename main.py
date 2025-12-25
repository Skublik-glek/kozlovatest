import sys
import time
from pathlib import Path

from rapidfuzz import fuzz

from PySide6.QtCore import QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout


ANSWERS_PATH = Path("answers.txt")

# Matching tuning
FUZZY_THRESHOLD = 80          # 0..100
MAX_QUERY_LEN = 2000

# Clipboard watching
POLL_MS = 250                 # polling interval
SELF_SUPPRESS_SEC = 1.0       # ignore events for a bit after we set clipboard

# Clipboard set race tuning
SET_DELAY_MS = 140            # delay before we set clipboard (lets source app finish copying)
RETRY_DELAY_MS = 220          # retry a bit later if clipboard got overwritten
MAX_SET_RETRIES = 2           # how many extra attempts to enforce our answer


def norm(s: str) -> str:
    return " ".join(s.lower().split())


class ClipWatch(QWidget):
    def __init__(self):
        super().__init__()

        # ---- UI ----
        self.setWindowTitle("Clipboard Watcher")
        self.setFixedSize(380, 140)

        self.label = QLabel("🟢 Активно\nЖду копирования…")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        # ---- Load answers ----
        if not ANSWERS_PATH.exists():
            self.label.setText(f"❌ answers.txt не найден:\n{ANSWERS_PATH.resolve()}")
            self.answers = []
            return

        raw = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw if line.strip()]

        # ---- Clipboard ----
        self.cb = QApplication.clipboard()

        # "external" = what user copied
        self.last_external = ""
        # what we last wrote
        self.last_set_by_us = ""
        # ignore clipboard changes until this time (monotonic)
        self.suppress_until = 0.0

        # Signals may or may not fire reliably on Wayland; we use both:
        self.cb.changed.connect(self.on_clipboard_changed)

        # Polling as fallback / reliability
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll_clipboard)
        self.timer.start()

        self.label.setText(
            f"🟢 Активно\n"
            f"Строк в answers.txt: {len(self.answers)}\n"
            f"Можно свернуть окно (не закрывать)."
        )
        print("▶ clipwatch started. Copy something…", flush=True)

    # ---- Clipboard reading (Wayland-friendly) ----
    def read_clipboard(self) -> str:
        # Force a request for clipboard data (helps on some Wayland setups)
        _ = self.cb.mimeData(QClipboard.Clipboard)
        return self.cb.text(QClipboard.Clipboard) or ""

    # ---- Watchers ----
    def poll_clipboard(self):
        self.process_text(self.read_clipboard(), source="poll")

    def on_clipboard_changed(self, mode: QClipboard.Mode):
        if mode != QClipboard.Clipboard:
            return
        self.process_text(self.read_clipboard(), source="signal")

    # ---- Core processing ----
    def process_text(self, text: str, source: str):
        now = time.monotonic()

        if not text:
            return

        # Ignore our own answer echo
        if text == self.last_set_by_us:
            return

        # Ignore changes while suppression window is active (after we set clipboard)
        if now < self.suppress_until:
            return

        # Ignore repeating same user copy
        if text == self.last_external:
            return

        self.last_external = text

        preview = text[:90].replace("\n", " ")
        print(f"[{source}] external clipboard: {preview!r}", flush=True)

        if len(text) > MAX_QUERY_LEN:
            print("⏭ skip: too long", flush=True)
            return

        q = norm(text)
        if not q:
            return

        # 1) Substring (case-insensitive)
        for line, ln in self.answers:
            if q in ln:
                self.set_answer(line, why="substring")
                return

        # 2) Fuzzy
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

    # ---- Clipboard writing with delay + verification + retries ----
    def set_answer(self, line: str, why: str):
        print(f"✔ MATCH ({why}): {line}", flush=True)

        # Set suppression so we don't react to our own clipboard write
        self.last_set_by_us = line
        self.suppress_until = time.monotonic() + SELF_SUPPRESS_SEC

        self.label.setText(
            f"🟢 Активно\n"
            f"Последний матч: {why}\n"
            f"Пытаюсь записать ответ в буфер…"
        )

        def attempt_set(try_idx: int):
            # Delay is handled outside; this function performs set + verifies
            self.cb.setText(line, QClipboard.Clipboard)
            QApplication.processEvents()

            current = self.read_clipboard()
            if current == line:
                print("✅ answer written to clipboard", flush=True)
                self.label.setText(
                    f"🟢 Активно\n"
                    f"Последний матч: {why}\n"
                    f"✅ Ответ скопирован в буфер"
                )
                return

            # If overwritten, retry a bit later
            if try_idx < MAX_SET_RETRIES:
                print(
                    f"⚠ clipboard overwritten after set (try {try_idx+1}). "
                    f"Retrying…",
                    flush=True
                )
                QTimer.singleShot(
                    RETRY_DELAY_MS,
                    lambda: attempt_set(try_idx + 1)
                )
            else:
                print("❌ failed to enforce clipboard after retries", flush=True)
                self.label.setText(
                    f"🟢 Активно\n"
                    f"Последний матч: {why}\n"
                    f"⚠ Не удалось записать в буфер (перезаписывают)"
                )

        # Key: set after a short delay to avoid racing with the source app's copy
        QTimer.singleShot(SET_DELAY_MS, lambda: attempt_set(0))


def main():
    app = QApplication(sys.argv)

    w = ClipWatch()
    w.show()  # Important on Wayland: having a real window improves clipboard behavior

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
