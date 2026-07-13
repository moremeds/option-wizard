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
from scripts._clients.fred import hy_oas_signal, FREDClient
try:
    sig = hy_oas_signal()
    print(json.dumps({k: v for k, v in sig.items() if k != "history"}, indent=2))
    print("last 5 obs:", sig["history"][-5:])
except Exception as e:
    print("FRED ERROR:", repr(e))
