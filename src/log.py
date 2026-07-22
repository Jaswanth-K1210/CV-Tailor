import logging
import os
from collections import deque

LOG_BUFFER: deque[str] = deque(maxlen=200)


class _MemHandler(logging.Handler):
    def __init__(self, buf: deque[str]):
        super().__init__()
        self._buf = buf

    def emit(self, record):
        try:
            msg = self.format(record)
            self._buf.append(msg)
        except Exception:
            pass


def setup_logging(level: int = logging.DEBUG) -> None:
    log_dir = os.path.expanduser("~/.cv-tailor")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "cv-tailor.log")

    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    root = logging.getLogger()
    root.setLevel(level)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)

    mh = _MemHandler(LOG_BUFFER)
    mh.setLevel(level)
    mh.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(mh)
