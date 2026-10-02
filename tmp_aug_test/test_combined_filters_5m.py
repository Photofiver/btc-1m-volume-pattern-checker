import json, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE="https://openapi.blofin.com/api/v1/market/candles"
trades=[
("MON-USDT","SHORT","2026-10-01T07:30:00Z",False),
("STX-USDT","SHORT","2026-10-01T08:00:00Z",True),
("APR-USDT","SHORT","2026-10-01T08:15:00Z",False),
("CAP-USDT","SHORT","2026-10-01T10:00:00Z",True),
("NOM-USDT","SHORT","2026-10-01T11:00:00Z",False),
("CAP-USDT","LONG","2026-10-01T11:00:00Z",False),
("MON-USDT","LONG","2026-10-01T12:00:00Z",True),
("CAP-USDT","SHORT","2026-10-01T12:00:00Z",False),
("CAP-USDT","LONG","2026-10-01T13:00:00Z",True),
("OPN-USDT","SHORT","2026-10-01T14:15:00Z",False),
("STX-USDT","LONG","2026-10-01T14:45:00Z",False),
("ALICE-USDT","LONG","2026-10-01T15:00:00Z",True),
("MEGA-USDT","LONG","2026-10-01T15:30:00Z",True),
("MON-USDT","LONG","2026-10-01T16:00:00Z",True),
("MOVR-USDT","LONG","2026-10-01T16:15:00Z",True),
("OPN-USDT","LONG","2026-10-01T17:30:00Z",False),
("CT-USDT","LONG","2026-10-01T18:30:00Z",False),
("CAP-USDT","SHORT","2026-10-01T18:45:00Z",True),
("ALICE-USDT","SHORT","2026-10-01T21:30:00Z",False),
("NOM-USDT","LONG","2026-10-01T21:30:00Z",True),
("CT-USDT","LONG","2026-10-01T22:45:00Z",True),
("UAI-USDT","LONG","2026-10-01T23:15:00Z",False),
("MEGA-USDT","LONG","2026-10-02T00:45:00Z",False),
("CT-USDT","LONG","2026-10-02T03:15:00Z",False),
]

def ms(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)

def fetch(inst, bar, after_ms, limit):
    q=urllib.parse.urlencode({"instId":inst,"bar":bar,"after":str(after_ms),"limit":str(limit)})
    req=urllib.request.Request(BASE+"?"+q,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        p=json.load(r)
    if str(p.get("code"))!="0": raise RuntimeError(p)
    out=[]
    for x in p.get("data",[]):
        if len(x)>=9 and str(x[8])=="1":
            out.append({"ts":int(x[0]),"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4]),"v":float(x[5])})
    return sorted(out,key=lambda z:z["ts"])

rows=[]
for inst,side,stamp,win in trades:
    close=ms(stamp)
    try:
        b15=fetch(inst,"15m",close+1000,40)
        sig_ts=close-15*60_000
        sig=next((x for x in b15 if x["ts"]==sig_ts),None)
        old_ts=sig_ts-10*15*60_000
        old=next((x for x in b15 if x["ts"]==old_ts),None)
        b1=fetch(inst,"1m",close+6*60_000,30)
        nxt=[x for x in b1 if close <= x["ts"] < close+5*60_000]
        if sig is None or old is None or len(nxt)!=5:
            rows.append({"inst":inst,"side":side,"stamp":stamp,"win":win,"error":f"sig={sig is not None} old={old is not None} next={len(nxt)}"})
            continue
        rng=sig["h"]-sig["l"]
        body_ratio=(abs(sig["c"]-sig["o"])/rng) if rng>0 else 0.0
        trend10=(sig["c"]/old["c"]-1.0)*100.0
        short_body=(sig["o"]-sig["c"])/sig["c"]*100.0
        if side=="LONG":
            base=(sig["c"]>sig["o"] and body_ratio>=0.60 and trend10>=2.0)
            confirm=max(x["h"] for x in nxt)>sig["h"]
        else:
            base=(sig["c"]<sig["o"] and short_body<=1.0)
            confirm=min(x["l"] for x in nxt)<sig["l"]
        combined=base and confirm
        rows.append({"inst":inst,"side":side,"stamp":stamp,"win":win,
          "body_ratio":round(body_ratio,6),"trend10_pct":round(trend10,6),
          "short_body_pct":round(short_body,6),"base_pass":base,
          "confirm5_pass":confirm,"combined_pass":combined,
          "signal_high":sig["h"],"signal_low":sig["l"],
          "next5_high":max(x["h"] for x in nxt),"next5_low":min(x["l"] for x in nxt)})
    except Exception as e:
        rows.append({"inst":inst,"side":side,"stamp":stamp,"win":win,"error":repr(e)})

def summ(side=None,key="combined_pass"):
    rr=[x for x in rows if "error" not in x and (side is None or x["side"]==side)]
    kept=[x for x in rr if x[key]]
    return {
      "total":len(rr),"kept":len(kept),
      "wins_kept":sum(1 for x in kept if x["win"]),
      "losses_kept":sum(1 for x in kept if not x["win"]),
      "wins_removed":sum(1 for x in rr if not x[key] and x["win"]),
      "losses_removed":sum(1 for x in rr if not x[key] and not x["win"]),
    }

out={"base_long":summ("LONG","base_pass"),"combined_long":summ("LONG","combined_pass"),
     "base_short":summ("SHORT","base_pass"),"combined_short":summ("SHORT","combined_pass"),
     "combined_all":summ(None,"combined_pass"),"rows":rows}
print(json.dumps(out,indent=2))
with open("tmp_aug_test/combined_filter_result.json","w") as f: json.dump(out,f,indent=2)
