"""Settings, loaded from the environment and an optional .env file at the repo root."""

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
VENDOR = ROOT / "vendor"
BENCH = ROOT / "bench"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    # Free-tier Gemini Flash models allow only 20 requests/day each (Pro: 0), far too few for agent runs.
    # Gemma 4 on the same API has far looser limits, so it is the default. Override in .env with a paid key.
    nav_model: str = field(default_factory=lambda: os.environ.get("A11Y_NAV_MODEL") or "gemma-4-26b-a4b-it")
    judge_model: str = field(default_factory=lambda: os.environ.get("A11Y_JUDGE_MODEL") or "gemma-4-26b-a4b-it")
    planner_model: str = field(default_factory=lambda: os.environ.get("A11Y_PLANNER_MODEL") or "gemma-4-26b-a4b-it")
    # Reference desktop size; P3 uses 320 CSS px (== 1280 px at 400% zoom, WCAG 1.4.10).
    desktop: tuple[int, int] = (1280, 800)
    zoom_viewport: tuple[int, int] = (320, 640)
    user_agent: str = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
    # Use the installed Chrome: several real sites refuse Playwright's bundled Chromium.
    browser_channel: str | None = field(default_factory=lambda: os.environ.get("A11Y_BROWSER_CHANNEL", "chrome") or None)
    headless: bool = field(default_factory=lambda: os.environ.get("A11Y_HEADLESS", "1") != "0")
    max_steps: int = 25
    explore_budget: int = field(default_factory=lambda: int(os.environ.get("A11Y_EXPLORE") or 15))  # pages to read before planning
    settle_ms: int = 600


SETTINGS = Settings()
