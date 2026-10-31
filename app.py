import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import akshare as ak

st.set_page_config(page_title="A股监控看板", layout="wide")
st.title("📊 专属A股监控看板")
st.caption(f"最后刷新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ================= 1. 核心指数 =================
def get_idx(code):
    try:
        r = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=5)
        r.encoding = "gbk"
        return float(r.text.split("~")[3])
    except:
        return 0.0

c1, c2, c3, c4 = st.columns(4)
sh_price = get_idx("sh000001")
c1.metric("上证指数", sh_price)
c2.metric("深证成指", get_idx("sz399001"))
c3.metric("恒生指数", get_idx("hkHSI"))
c4.metric("恒生科技", get_idx("hkHSTECH"))

# ================= 2. 北向资金总结 =================
st.subheader("💰 北向资金流向")
@st.cache_data(ttl=900)
def get_north_summary():
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        # 兼容不同版本的列名
        col_dir = '资金方向' if '资金方向' in df.columns else '类型'
        north_row = df[df[col_dir] == '北向']
        if not north_row.empty:
            net_buy = float(north_row['成交净买额'].iloc[0])
            return net_buy
    except:
        pass
    return None

north_net = get_north_summary()
if north_net is not None:
    if north_net > 0:
        st.success(f"今日北向资金**净流入**：{north_net:.2f} 亿元")
    else:
        st.error(f"今日北向资金**净流出**：{abs(north_net):.2f} 亿元")
else:
    st.info("北向资金数据暂不可用（服务器接口被限流或休市）。")

# ================= 3. 自选基金 T+1 判断 =================
st.subheader("💰 自选基金每日判断")
fund_codes = st.text_input("输入自选基金代码 (逗号分隔)", "110011,161725")

@st.cache_data(ttl=3600)
def analyze_fund(code):
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        nav = pd.to_numeric(df["单位净值"], errors="coerce").dropna().tail(60).values
        if len(nav) < 30: return None
        mom = (nav[-1] / nav[-20] - 1) * 100
        logn = np.log(nav)
        x = np.arange(len(logn))
        slope, intercept = np.polyfit(x, logn, 1)
        ss_res = np.sum((logn - (slope * x + intercept)) ** 2)
        ss_tot = np.sum((logn - logn.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        dev = (nav[-1] / nav.mean() - 1) * 100
        
        if mom > 0 and r2 > 0.3 and dev > -3: verdict = "🟢 持有逻辑维持"
        elif mom < 0 and dev < -5 and r2 < 0.2: verdict = "🔴 逻辑可能已破坏"
        else: verdict = "🟡 逻辑转弱 / 观察"
        return {"代码": code, "20日动量(%)": round(mom, 2), "趋势R²": round(r2, 2), "结论": verdict}
    except:
        return None

if fund_codes:
    results = [analyze_fund(c.strip()) for c in fund_codes.split(",") if c.strip()]
    results = [r for r in results if r]
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.info("未能获取基金净值数据，请核对代码。")

# ================= 4. 板块每日定性审查 =================
st.subheader("🔥 板块定性（中期趋势 / 短期题材）")
st.caption("每天自动审查所有行业板块，仅显示符合趋势或题材特征的板块。")

@st.cache_data(ttl=1800)
def get_filtered_sectors():
    try:
        # 获取全市场行业板块当日数据
        df = ak.stock_board_industry_name_em()
        
        results = []
        for _, row in df.iterrows():
            try:
                chg = float(row.get("涨跌幅", 0) or 0)
            except:
                chg = 0.0
                
            # 过滤条件：只要符合短期或中期的
            tag = ""
            if chg >= 3.0:
                tag = "⚡ 短期题材 (资金脉冲)"
            elif 0.5 <= chg < 3.0:
                tag = "📈 中期趋势 (温和上行)"
            else:
                continue # 不符合的，直接跳过不显示
                
            results.append({
                "板块名称": row.get("板块名称", ""),
                "当日涨跌幅(%)": chg,
                "定性判断": tag,
                "领涨股": row.get("领涨股票", "")
            })
            
        # 按涨幅从高到低排序
        res_df = pd.DataFrame(results)
        if not res_df.empty:
            res_df = res_df.sort_values(by="当日涨跌幅(%)", ascending=False)
        return res_df
    except Exception as e:
        return None

filtered_sectors = get_filtered_sectors()
if filtered_sectors is not None and not filtered_sectors.empty:
    st.dataframe(filtered_sectors, use_container_width=True, hide_index=True)
else:
    st.info("今日暂无符合中线趋势或短期题材特征的强势板块，或数据获取失败。")
