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
for t in ["QQQ", "NVDA", "TSLA"]:
    try:
        ivr = c.iv_rank(t)
        ts = c.iv_term_structure(t)
        skew = c.historical_risk_reversal_skew(t)
        print(f"\n=== {t} ===")
        print("iv_rank:", json.dumps(ivr)[:600])
        print("term_structure:", json.dumps(ts)[:600])
        print("skew:", json.dumps(skew)[:400])
    except Exception as e:
        print(f"{t}: ERROR {e}")
