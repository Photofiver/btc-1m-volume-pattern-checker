import io, json, zipfile, hashlib, urllib.request
import numpy as np
import pandas as pd

URL="https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip"
SHA="85b174d0c091ab904341f1cce2f31fd88ebd0f10631678238756aa72d5d9897a"
START=pd.Timestamp("2026-08-09T19:15:00Z")
END=pd.Timestamp("2026-08-16T19:15:00Z")
FEE=0.0006
QTY=0.01

def rma(s,n):
    s=pd.Series(s,dtype=float); a=s.to_numpy(); out=np.full(len(a),np.nan)
    seed=None
    for i in range(n-1,len(a)):
        w=a[i-n+1:i+1]
        if np.isfinite(w).all():
            seed=i; out[i]=w.mean(); break
    if seed is None: return pd.Series(out,index=s.index)
    prev=out[seed]
    for i in range(seed+1,len(a)):
        if np.isfinite(a[i]):
            prev=(prev*(n-1)+a[i])/n
            out[i]=prev
    return pd.Series(out,index=s.index)

def ema(s,n):
    return pd.Series(s,dtype=float).ewm(span=n,adjust=False,min_periods=1).mean()

def build_features(df):
    o,h,l,c,v=[df[x].astype(float) for x in ["Open","High","Low","Close","Volume"]]
    m=ema(c,12)-ema(c,26); sig=ema(m,9); hist=m-sig
    ll=l.rolling(14).min(); hh=h.rolling(14).max()
    rawk=100*(c-ll)/(hh-ll); k=rawk.rolling(3).mean(); sd=k.rolling(3).mean(); kd=k-sd
    pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    up=h-h.shift(1); dn=l.shift(1)-l
    pdm=pd.Series(np.where((up>dn)&(up>0),up,0.0),index=df.index)
    mdm=pd.Series(np.where((dn>up)&(dn>0),dn,0.0),index=df.index)
    atr=rma(tr,14); pdi=100*rma(pdm,14)/atr; mdi=100*rma(mdm,14)/atr
    adx=rma(100*(pdi-mdi).abs()/(pdi+mdi),14)
    lg=lr=np.nan; gr=[]
    for oi,ci,vi in zip(o,c,v):
        if ci>oi: lg=vi
        elif ci<oi: lr=vi
        gr.append(lg/lr if np.isfinite(lg) and np.isfinite(lr) and lr>0 else np.nan)
    gr=pd.Series(gr,index=df.index)
    obv=(np.sign(c.diff()).fillna(0)*v).cumsum()
    X=pd.DataFrame({
      "MACD":m,"Signal":sig,"Histogram":hist,"K":k,"D":sd,"K_D":kd,"ADX":adx,"GreenRed":gr,
      "Return1_pct":(c/c.shift(1)-1)*100,"Return3_pct":(c/c.shift(3)-1)*100,
      "Range_pct":(h/l-1)*100,"Body_pct":(c/o-1)*100,"Volume":v,
      "Volume_vs_MA20_pct":(v/v.rolling(20).mean()-1)*100,
      "OBV_1":obv-obv.shift(1),"OBV_3":obv-obv.shift(3),"OBV_20":obv-obv.shift(20),
      "OBV_40":obv-obv.shift(40),"OBV_80":obv-obv.shift(80)})
    return X

def pred(row,model):
    n=0
    while model["F"][n]>=0:
        f=model["features"][model["F"][n]]
        n=model["L"][n] if row[f] <= model["T"][n] else model["R"][n]
    return model["C"][n]

with urllib.request.urlopen(URL,timeout=90) as r: blob=r.read()
got=hashlib.sha256(blob).hexdigest()
if got!=SHA: raise RuntimeError(f"SHA mismatch {got}")
with zipfile.ZipFile(io.BytesIO(blob)) as z: raw=z.read(z.namelist()[0])

cols=["open_time","Open","High","Low","Close","Volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
df=pd.read_csv(io.BytesIO(raw),header=None,names=cols)
unit="us" if float(df.open_time.iloc[0])>1e14 else "ms"
df["time"]=pd.to_datetime(df.open_time,unit=unit,utc=True)
df=df.sort_values("time").reset_index(drop=True)
X=build_features(df).replace([np.inf,-np.inf],np.nan)
model=json.load(open("tmp_aug_test/separator_model.json"))
for k,v in model["M"].items(): X[k]=X[k].fillna(v)

op=df.Open.astype(float)
entry=op.shift(-1); exitp=op.shift(-2)
pnl=QTY*(exitp-entry)-FEE*QTY*(entry+exitp)
win=pnl>0

window=(df.time>=START)&((df.time+pd.Timedelta(minutes=10))<END)
base=window&(X.OBV_80>0)
signals=[]
for i in np.where(base.to_numpy())[0]:
    if pred(X.iloc[i],model)==1: signals.append(i)
wins=[i for i in signals if bool(win.iloc[i])]
losses=[i for i in signals if not bool(win.iloc[i])]
out={
 "source":"Binance Spot BTCUSDT 5m monthly archive",
 "sha256":got,"archive_rows":int(len(df)),
 "period_utc":[START.isoformat(),END.isoformat()],
 "possible_entries":int(window.sum()),
 "obv80_positive_candidates":int(base.sum()),
 "signals":len(signals),"wins":len(wins),"losses":len(losses),
 "win_rate_pct":round(100*len(wins)/len(signals),6) if signals else None,
 "net_usdt_0_01btc":round(float(pnl.iloc[signals].sum()),6) if signals else 0.0,
 "detail":[{"signal_time_utc":df.time.iloc[i].isoformat(),"pnl_usdt":round(float(pnl.iloc[i]),6),"win":bool(win.iloc[i])} for i in signals]
}
open("tmp_aug_test/aug_result.json","w").write(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!="detail"},indent=2))
