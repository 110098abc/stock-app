```python
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(page_title="A股板块监测", layout="wide")

@st.cache_data(ttl=1800)
def get_indexes():
    import akshare as ak
    out = {}
    for code, name in [("sh000001", "上证指数"), ("sz399001", "深证成指")]:
        try:
            df = ak.stock_zh_index_daily(symbol=code)
            out[name] = round(float(df.iloc[-1]["close"]), 2)
        except Exception:
            out[name] = None
    for code, name in [("hkHSI", "恒生指数"), ("hkHSTECH", "恒生科技")]:
        try:
            r = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=10)
            r.encoding = "gbk"
            out[name] = round(float(r.text.split("~")[3]), 2)
        except Exception:
            out[name] = None
    return out

@st.cache_data(ttl=3600)
def get_us_treasury():
    import akshare as ak
    try:
        df = ak.bond_zh_us_rate()
        df = df.dropna(subset=["美国国债收益率10年", "美国国债收益率30年"])
        last = df.iloc[-1]
        return {
            "10Y": round(float(last["美国国债收益率10年"]), 3),
            "30Y": round(float(last["美国国债收益率30年"]), 3),
            "hist10": df["美国国债收益率10年"].tail(30).tolist(),
        }
    except Exception:
        return {"10Y": None, "30Y": None, "hist10": []}

@st.cache_data(ttl=3600)
def get_sectors():
    try:
        from zzshare.client import DataApi
        api = DataApi()
        today = datetime.now().strftime("%Y%m%d")
        rows = []
        for ptype, label in [(17, "题材"), (14, "行业")]:
            try:
                rank = api.plates_rank(plate_type=ptype, date1=today, limit=20)
                for _, r in rank.iterrows():
                    rows.append({
                        "板块": r.get("板块名称", ""),
                        "类别": label,
                        "涨幅%": round(float(r.get("涨幅", 0) or 0), 2),
                    })
            except Exception:
                continue
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()

def classify_sector(df):
    if df.empty: return df
    def tag(x):
        if abs(x) >= 3: return "短期题材"
        elif 0 < abs(x) < 3: return "中线趋势观察"
        return "待观察"
    df["标签"] = df["涨幅%"].apply(tag)
    return df

@st.cache_data(ttl=3600)
def analyze_fund(code):
    import akshare as ak
    try:
        df = ak.fund_open_fund_info_em(code, "单位净值走势")
        nav = pd.to_numeric(df["单位净值"], errors="coerce").dropna().tail(60).values
        if len(nav) < 30: return None
        mom = (nav[-1] / nav[-20] - 1) * 100
        logn = np.log(nav)
        x = np.arange(len(logn))
        slope, intercept = np.polyfit(x, logn, 1)
        pred = slope * x + intercept
        ss_res = np.sum((logn - pred) ** 2)
        ss_tot = np.sum((logn - logn.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        dev = (nav[-1] / nav.mean() - 1) * 100
        
        if mom > 0 and r2 > 0.3 and dev > -3: verdict = "持有逻辑维持"
        elif mom < 0 and dev < -5 and r2 < 0.2: verdict = "逻辑可能已破坏"
        else: verdict = "逻辑转弱，进入观察"
        
        return {"代码": code, "20日动量%": round(mom, 2), "趋势R²": round(r2, 2), "均线偏离%": round(dev, 2), "判断": verdict}
    except Exception:
        return None

st.title("📊 A股与基金监控看板")
st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

idx = get_indexes()
us = get_us_treasury()

st.subheader("核心指数与美债")
c = st.columns(6)
for i, k in enumerate(["上证指数", "深证成指", "恒生指数", "恒生科技"]):
    c[i].metric(k, idx.get(k) if idx.get(k) else "—")
c[4].metric("10Y美债", f"{us['10Y']}%" if us['10Y'] else "—")
c[5].metric("30Y美债", f"{us['30Y']}%" if us['30Y'] else "—")

LEVELS = {"上证指数": [3700, 3650, 3600, 3500], "深证成指": [12000, 11500, 11000]}
alerts = []
for name, levels in LEVELS.items():
    p = idx.get(name)
    if not p: continue
    for lv in levels:
        if abs(p - lv) / lv <= 0.005:
            alerts.append(f"{name} {'失守' if p < lv else '站上'} {lv}点，当前 {p}")
if alerts:
    st.subheader("⚠️ 关键位提醒")
    for a in alerts: st.warning(a)

if us["hist10"]:
    st.line_chart(pd.DataFrame({"10Y美债收益率": us["hist10"]}))

st.subheader("板块分类看板")
sdf = classify_sector(get_sectors())
if not sdf.empty:
    for t in ["短期题材", "中线趋势观察", "待观察"]:
        sub = sdf[sdf["标签"] == t]
        if not sub.empty:
            st.markdown(f"**{t}**")
            st.dataframe(sub[["板块", "类别", "涨幅%"]], use_container_width=True, hide_index=True)
else:
    st.info("板块数据暂不可用，请稍后刷新。")

st.subheader("自选基金每日判断")
codes_input = st.text_input("输入基金代码（用英文逗号分隔）", "110011,161725")
if codes_input:
    results = []
    for code in [c.strip() for c in codes_input.split(",") if c.strip()]:
        r = analyze_fund(code)
        if r: results.append(r)
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        st.caption("依据：近20日动量 + 60日趋势R² + 均线偏离。仅供参考。")
    else:
        st.info("未能获取基金数据，请检查代码。")
```
