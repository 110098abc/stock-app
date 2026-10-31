import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(page_title="A股监测", layout="wide")
st.title("📊 我的专属A股监控看板")
st.caption(f"最后刷新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

def get_idx(code):
    try:
        r = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=5)
        r.encoding = "gbk"
        return float(r.text.split("~")[3])
    except:
        return 0.0

st.subheader("🌐 核心指数与美债")
c1, c2, c3, c4 = st.columns(4)
sh_price = get_idx("sh000001")
c1.metric("上证指数", sh_price)
c2.metric("深证成指", get_idx("sz399001"))
c3.metric("恒生指数", get_idx("hkHSI"))
c4.metric("恒生科技", get_idx("hkHSTECH"))

@st.cache_data(ttl=3600)
def get_us_bond():
    try:
        import akshare as ak
        df = ak.bond_zh_us_rate()
        df = df.dropna()
        return float(df.iloc[-1]["美国国债收益率10年"]), float(df.iloc[-1]["美国国债收益率30年"])
    except:
        return 0.0, 0.0

us10, us30 = get_us_bond()
c5, c6 = st.columns(2)
c5.metric("10年期美债收益率", f"{us10}%" if us10 > 0 else "获取失败")
c6.metric("30年期美债收益率", f"{us30}%" if us30 > 0 else "获取失败")

if sh_price > 0:
    if sh_price < 3700:
        st.error(f"🚨 关键警报：上证指数当前 {sh_price}，已失守 3700 点关口，由攻转守需警惕！")
    elif sh_price < 3750:
        st.warning(f"⚠️ 关键提醒：上证指数当前 {sh_price}，逼近 3700 点防守位。")
    else:
        st.success(f"✅ 指数处于安全区间：上证指数当前 {sh_price}。")

st.subheader("🔥 板块分类看板")
@st.cache_data(ttl=1800)
def get_sectors():
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        df = df.sort_values(by="涨跌幅", ascending=False)
        return df.head(10)
    except:
        return None

sector_df = get_sectors()
if sector_df is not None:
    def tag_sector(x):
        if x >= 3: return "短期题材"
        elif 1 <= x < 3: return "中线趋势"
        else: return "周期波段/待观察"
    
    sector_df["当前定性"] = sector_df["涨跌幅"].apply(tag_sector)
    st.dataframe(sector_df[["板块名称", "涨跌幅", "当前定性"]], use_container_width=True, hide_index=True)
else:
    st.info("板块数据暂时获取失败，请稍后刷新。")

st.subheader("💰 自选基金每日判断")
fund_codes = st.text_input("输入你的自选基金代码（用英文逗号分隔，例如：110011,161725）", "110011,161725")

@st.cache_data(ttl=3600)
def analyze_fund(code):
    try:
        import akshare as ak
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
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
        
        if mom > 0 and r2 > 0.3 and dev > -3:
            verdict = "🟢 持有逻辑维持"
        elif mom < 0 and dev < -5 and r2 < 0.2:
            verdict = "🔴 逻辑可能已破坏"
        else:
            verdict = "🟡 逻辑转弱，进入观察"
            
        return {"基金代码": code, "20日动量%": round(mom, 2), "趋势R²": round(r2, 2), "均线偏离%": round(dev, 2), "判断结论": verdict}
    except:
        return None

if fund_codes:
    results = []
    for code in [c.strip() for c in fund_codes.split(",") if c.strip()]:
        res = analyze_fund(code)
        if res: results.append(res)
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        st.caption("依据：近20日动量 + 60日趋势R² + 均线偏离计算。仅供参考。")
    else:
        st.info("未能获取基金数据，请检查代码是否正确。")
