import json, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE="https://openapi.blofin.com/api/v1/market/candles"
entries=[
("CAP-USDT","2026-10-01T11:00:00Z","LOSS"),
("MON-USDT","2026-10-01T12:00:00Z","WIN"),
("CAP-USDT","2026-10-01T13:00:00Z","WIN"),
("STX-USDT","2026-10-01T14:45:00Z","LOSS"),
("ALICE-USDT","2026-10-01T15:00:00Z","WIN"),
("MEGA-USDT","2026-10-01T15:30:00Z","WIN"),
("MON-USDT","2026-10-01T16:00:00Z","WIN"),
("MOVR-USDT","2026-10-01T16:15:00Z","WIN"),
("OPN-USDT","2026-10-01T17:30:00Z","LOSS"),
("CT-USDT","2026-10-01T18:30:00Z","LOSS"),
("NOM-USDT","2026-10-01T21:30:00Z","WIN"),
("CT-USDT","2026-10-01T22:45:00Z","WIN"),
("UAI-USDT","2026-10-01T23:15:00Z","LOSS"),
("MEGA-USDT","2026-10-02T00:45:00Z","LOSS"),
("CT-USDT","2026-10-02T03:15:00Z","LOSS"),
]

def ms(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)

def fetch(inst, close_ms):
    # ask for candles earlier than 6 min after signal close; 30 bars covers signal 15m + 5m window
    params=urllib.parse.urlencode({"instId":inst,"bar":"1m","after":str(close_ms+6*60_000),"limit":"30"})
    req=urllib.request.Request(BASE+"?"+params,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        payload=json.load(r)
    if str(payload.get("code"))!="0":
        raise RuntimeError(payload)
    rows=[]
    for x in payload.get("data",[]):
        if len(x)>=9 and str(x[8])=="1":
            rows.append({"ts":int(x[0]),"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4])})
    return rows

out=[]
for inst, stamp, original in entries:
    close=ms(stamp)
    try:
        rows=fetch(inst,close)
        sig=[x for x in rows if close-15*60_000 <= x["ts"] < close]
        nxt=[x for x in rows if close <= x["ts"] < close+5*60_000]
        if len(sig)!=15 or len(nxt)!=5:
            out.append({"inst":inst,"signal_close":stamp,"original":original,"error":f"bars sig={len(sig)} next={len(nxt)}"})
            continue
        signal_high=max(x["h"] for x in sig)
        next_high=max(x["h"] for x in nxt)
        passed=next_high>signal_high
        first_break=None
        for x in sorted(nxt,key=lambda z:z["ts"]):
            if x["h"]>signal_high:
                first_break=datetime.fromtimestamp(x["ts"]/1000,tz=timezone.utc).isoformat()
                break
        out.append({"inst":inst,"signal_close":stamp,"original":original,"signal_high":signal_high,"next5_high":next_high,"passed":passed,"first_break_utc":first_break})
    except Exception as e:
        out.append({"inst":inst,"signal_close":stamp,"original":original,"error":repr(e)})

summary={
"total":len(entries),
"valid":sum(1 for x in out if "passed" in x),
"would_enter":sum(1 for x in out if x.get("passed") is True),
"would_skip":sum(1 for x in out if x.get("passed") is False),
"wins_enter":sum(1 for x in out if x.get("passed") is True and x.get("original")=="WIN"),
"losses_enter":sum(1 for x in out if x.get("passed") is True and x.get("original")=="LOSS"),
"wins_skip":sum(1 for x in out if x.get("passed") is False and x.get("original")=="WIN"),
"losses_skip":sum(1 for x in out if x.get("passed") is False and x.get("original")=="LOSS"),
}
res={"summary":summary,"entries":out}
print(json.dumps(res,indent=2))
with open("tmp_aug_test/long_breakout_result.json","w") as f: json.dump(res,f,indent=2)
