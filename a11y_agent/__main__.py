"""CLI.

  python -m a11y_agent run <url> [--tasks 4] [--profiles P1,P2,P3]   full pipeline on any site (needs OPENROUTER_API_KEY, see .env.example)
                                       [--no-agents] [--all-checks]      rule checks only / ignore the planner's check selection
  python -m a11y_agent models                                               list Gemini models available to your key
  python -m a11y_agent bench                                                serve the local benchmark app and print its URL
"""

import argparse
import sys
import time


def main(argv=None):
    ap = argparse.ArgumentParser(prog="a11y_agent", description="Task-based accessibility testing with profile agents.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="test a web application, given only its URL")
    r.add_argument("url")
    r.add_argument("--tasks", type=int, default=4)
    r.add_argument("--profiles", default="P1,P2,P3,P4,P5")
    r.add_argument("--no-agents", action="store_true", help="skip profile agents; only step checks on the reference path")
    r.add_argument("--run-dir", default="", help="where to write results (default runs/<timestamp>)")
    r.add_argument("--all-checks", action="store_true", help="keep every check group, ignoring the planner's choice")
    d = sub.add_parser("dashboard", help="web dashboard: start runs, watch them live, read reports")
    d.add_argument("--port", type=int, default=8800)
    sub.add_parser("models", help="list Gemini models available to your key")
    sub.add_parser("bench", help="serve the benchmark app locally")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        from .pipeline import run_url
        from pathlib import Path
        out = run_url(a.url, a.tasks, tuple(a.profiles.split(",")), out_dir=Path(a.run_dir) if a.run_dir else None,
                      agents=not a.no_agents, all_checks=a.all_checks)
        print(f"Report: {out / 'report.md'}")
    elif a.cmd == "dashboard":
        from .dashboard import serve_dashboard
        serve_dashboard(a.port)
    elif a.cmd == "models":
        from .llm import LLM
        for m in LLM().list_models():
            print(m)
    elif a.cmd == "bench":
        from .benchserver import serve
        url, httpd = serve(8765)
        print(f"BenchBook running at {url}  (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
