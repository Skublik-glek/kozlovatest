import os
import sys
from pathlib import Path

from rapidfuzz import fuzz
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication


ANSWERS_PATH = Path("answers.txt")
FUZZY_THRESHOLD = 80
MAX_QUERY_LEN = 2000

# Если True — при старте отцепиться от терминала (демонизация)
DAEMONIZE = True


def norm(s: str) -> str:
    return " ".join(s.lower().split())


def daemonize():
    """
    Классическая демонизация для Linux:
    - fork 2 раза
    - setsid
    - stdin/stdout/stderr -> /dev/null
    """
    if os.environ.get("CLIPWATCH_NO_DAEMON") == "1":
        return

    # 1st fork
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    os.setsid()
    os.umask(0)

    # 2nd fork
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    # Redirect stdio to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()
    with open("/dev/null", "rb", 0) as f_in, open("/dev/null", "ab", 0) as f_out:
        os.dup2(f_in.fileno(), sys.stdin.fileno())
        os.dup2(f_out.fileno(), sys.stdout.fileno())
        os.dup2(f_out.fileno(), sys.stderr.fileno())


class ClipWatch:
    def __init__(self, app: QGuiApplication):
        if not ANSWERS_PATH.exists():
            raise FileNotFoundError(f"Не найден {ANSWERS_PATH.resolve()}")

        raw_lines = ANSWERS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        self.answers = [(line, norm(line)) for line in raw_lines if line.strip()]

        self.app = app
        self.cb = app.clipboard()
        self.last = ""

        # сигнал на изменение буфера
        self.cb.dataChanged.connect(self.on_clipboard_changed)

    def on_clipboard_changed(self):
        text = self.cb.text() or ""
        if text == self.last:
            return

        self.last = text

        if not text or len(text) > MAX_QUERY_LEN:
            return

        q = norm(text)
        if not q:
            return

        # 1) Подстрока (без регистра)
        found = None
        for line, ln in self.answers:
            if q in ln:
                found = line
                break

        # 2) Fuzzy, если не нашли
        if found is None:
            best_score = 0
            best_line = None
            for line, ln in self.answers:
                score = fuzz.token_set_ratio(q, ln)
                if score > best_score:
                    best_score = score
                    best_line = line
            if best_score >= FUZZY_THRESHOLD:
                found = best_line

        if found:
            # кладём найденную строку обратно в буфер
            self.cb.setText(found)
            self.last = found


def main():
    if DAEMONIZE:
        daemonize()

    # Нужна графическая сессия (Wayland/X11), но окна мы не показываем
    app = QGuiApplication(sys.argv)

    watcher = ClipWatch(app)

    # Чтобы приложение не выходило сразу:
    # (Qt живёт на event loop)
    QTimer.singleShot(0, lambda: None)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
