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
try:
    ivr = c.iv_rank("VIX")["data"]
    print("VIX iv_rank latest:", ivr[-1] if ivr else "EMPTY")
except Exception as e:
    print("VIX ERROR:", repr(e))
