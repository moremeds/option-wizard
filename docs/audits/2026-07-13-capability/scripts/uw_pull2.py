import sys, os, json
sys.path.insert(0, "plugins/option-wizard/skills/option-wizard")

def load_env(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env(".env")
from scripts._clients.uw import UWClient

c = UWClient()
for t in ["QQQ", "NVDA", "TSLA", "SPX"]:
    print(f"\n=== {t} ===")
    try:
        ivr = c.iv_rank(t)["data"]
        last = ivr[-1]
        print("iv_rank latest:", last)
    except Exception as e:
        print("iv_rank ERROR:", e)
    try:
        ts = c.iv_term_structure(t)["data"]
        # filter today's date rows, sort by dte
        today_rows = [r for r in ts if r["date"] == ts[0]["date"]]
        today_rows_sorted = sorted(today_rows, key=lambda r: r["dte"])
        print("term structure (date=%s), dte:vol pairs:" % ts[0]["date"])
        for r in today_rows_sorted[:12]:
            print("  dte=%s vol=%s" % (r["dte"], r["volatility"]))
    except Exception as e:
        print("term_structure ERROR:", e)
    try:
        sk = c.historical_risk_reversal_skew(t)["data"]
        print("skew latest:", sk[-1])
    except Exception as e:
        print("skew ERROR:", e)
