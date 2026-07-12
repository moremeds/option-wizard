import json, sys
sys.path.insert(0, "plugins/option-wizard/skills/option-wizard")
from scripts.gex_levels import compute_levels

def load(path):
    with open(path) as f:
        d = json.load(f)
    return d["result"] if isinstance(d, dict) and "result" in d else d

spx_rows = load("/Users/chenxi/.claude/projects/-Users-chenxi-projects-option-wizard/f786956f-6c57-46e9-b5e9-4bca0b9772a3/tool-results/mcp-unusual-whales-get_greek_exposure_by_strike-1783877479279.txt")
qqq_rows = load("/Users/chenxi/.claude/projects/-Users-chenxi-projects-option-wizard/f786956f-6c57-46e9-b5e9-4bca0b9772a3/tool-results/mcp-unusual-whales-get_greek_exposure_by_strike-1783877484114.txt")

print("SPX rows:", len(spx_rows), "date:", spx_rows[0]["date"])
print("QQQ rows:", len(qqq_rows), "date:", qqq_rows[0]["date"])

spx_spot = 7543.64  # Thu 7/9 close, stale proxy - see caveat
qqq_spot = 723.28    # Thu 7/9 close, stale proxy - see caveat

for name, rows, spot in [("SPX", spx_rows, spx_spot), ("QQQ", qqq_rows, qqq_spot)]:
    lv = compute_levels(rows, spot, call_wall_definition="net_neg_gex", chain_source="UW MCP get_greek_exposure_by_strike", chain_timestamp=rows[0]["date"])
    lv_oi = compute_levels(rows, spot, call_wall_definition="oi_cluster", chain_source="UW MCP get_greek_exposure_by_strike", chain_timestamp=rows[0]["date"])
    print(f"\n=== {name} (spot proxy {spot}) ===")
    print("gamma_flip:", lv["gamma_flip"])
    print("put_wall:", lv["put_wall"])
    print("call_wall (net_neg_gex):", lv["call_wall"])
    print("call_wall (oi_cluster):", lv_oi["call_wall"])
    # total net gex sign at spot-ish
    total_net = sum(float(r.get("call_gex",0)) + float(r.get("put_gex",0)) for r in rows)
    print("sum net gex all strikes:", total_net)
