"""Append-only event log (runs/<id>/events.jsonl) that the dashboard reads live."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class EventLog:
    def __init__(self, run_dir: Path | None):
        self.path = run_dir / "events.jsonl" if run_dir else None
        self.live_dir = run_dir / "live" if run_dir else None  # latest screenshot per agent, for the dashboard
        self._lock = threading.Lock()
        self._shot_n: dict[str, int] = {}
        self.t0 = time.time()

    def snapshot(self, session, name: str) -> bool:
        """Save what a browser shows now as live/<name>.jpg. Only for people watching; never shown to an agent."""
        if not self.live_dir:
            return False
        try:
            self.live_dir.mkdir(exist_ok=True)
            data = session.page.screenshot(type="jpeg", quality=55, timeout=5000)
            tmp = self.live_dir / f".{name}.tmp"
            tmp.write_bytes(data)
            os.replace(tmp, self.live_dir / f"{name}.jpg")
            if os.environ.get("A11Y_KEEP_SHOTS") == "1":   # 11 Nov 2026: also keep every step's view, for the paper
                with self._lock:
                    self._shot_n[name] = n = self._shot_n.get(name, 0) + 1
                steps = self.live_dir / "steps"
                steps.mkdir(exist_ok=True)
                (steps / f"{name}_{n:03d}.jpg").write_bytes(data)
            return True
        except Exception:
            return False

    def emit(self, kind: str, **data) -> None:
        rec = {"t": round(time.time(), 2), "elapsed": round(time.time() - self.t0, 1), "kind": kind, **data}
        line = json.dumps(rec, ensure_ascii=False, default=str)
        print(f"[{rec['elapsed']:7.1f}s] {kind} " + " ".join(f"{k}={str(v)[:80]}" for k, v in data.items()), flush=True)
        if self.path:
            with self._lock, self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


NULL = EventLog(None)
