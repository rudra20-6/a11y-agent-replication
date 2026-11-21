"""Every scripted path completes on the clean app, and (with a mouse) under every barrier of a catalog
(--catalog ma11y_path for the paper's 23; MP_F36_T3 breaks the path by design). Run from the package root."""
import sys, traceback
sys.path.insert(0, '.')
from a11y_agent.benchserver import serve
from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.bench import CATALOGS, load_tasks, load_mutants, install_mutant, replay_gold, succeeded

def run(pool, base, task, mutant=None):
    s = pool.session(Viewport(1280, 800))
    errs = []
    s.page.on("pageerror", lambda e: errs.append(str(e)[:120]))
    install_mutant(s, mutant)
    try:
        s.goto(base + task.start)
        replay_gold(s, task)
        ok = succeeded(s, task)
    except Exception as e:
        ok = False; errs.append(str(e).splitlines()[0][:160])
    s.close()
    return ok, errs

if __name__ == "__main__":
    base, httpd = serve(); pool = BrowserPool()
    cat = sys.argv[sys.argv.index('--catalog') + 1] if '--catalog' in sys.argv else 'dev'
    tasks, muts = load_tasks(), load_mutants(CATALOGS[cat])
    bad = 0
    for t in tasks.values():
        ok, errs = run(pool, base, t); bad += not ok
        print(f"clean  {t.id:22s} {'PASS' if ok else 'FAIL'} {errs}")
    for m in muts.values():
        ok, errs = run(pool, base, tasks[m.task], m); bad += not ok
        print(f"mutant {m.id:22s} on {m.task:22s} {'PASS' if ok else 'FAIL'} {errs}")
    pool.close(); httpd.shutdown()
    print("FAILURES:", bad)
