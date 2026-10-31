import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(page_title="A股与北向资金联动看板", layout="wide")
st.title("📊 专属A股 · 北向资金与板块联动看板")
st.caption(f"最后刷新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 1. 核心指数
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

# 2. 北向资金与板块交互看板
st.subheader("💰 北向资金与板块流向")

import akshare as ak

@st.cache_data(ttl=900)
def get_north_summary():
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        north_row = df[(df['资金方向'] == '北向') & (df['类型'] == '合计')]
        if not north_row.empty:
            return float(north_row['成交净买额'].iloc[0])
    except:
        pass
    return None

@st.cache_data(ttl=900)
def get_north_board_flow(direction="净流入"):
    try:
        df = ak.stock_hsgt_board_rank_em(symbol="北向资金增持行业板块排行", indicator="今日")
        sort_col = "北向资金今日增持估计-市值"
        if sort_col in df.columns:
            if direction == "净流入":
                df = df.sort_values(by=sort_col, ascending=False)
            else:
                df = df.sort_values(by=sort_col, ascending=True)
        rename_map = {
            "名称": "行业板块",
            "最新涨跌幅": "当日涨跌幅(%)",
            sort_col: "北向今日增持估计(亿元)"
        }
        show_cols = [c for c in rename_map.keys() if c in df.columns]
        out = df[show_cols].head(10).rename(columns=rename_map)
        if "北向今日增持估计(亿元)" in out.columns:
            out["北向今日增持估计(亿元)"] = (out["北向今日增持估计(亿元)"] / 1e8).round(2)
        return out
    except Exception as e:
        return None

@st.cache_data(ttl=900)
def get_sector_main_flow():
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        cols = ["名称", "今日涨跌幅", "主力净流入-净额"]
        show_cols = [c for c in cols if c in df.columns]
        out = df[show_cols].copy()
        if "主力净流入-净额" in out.columns:
            out["主力净流入-净额"] = (out["主力净流入-净额"] / 1e8).round(2)
        return out.rename(columns={"名称": "行业板块", "今日涨跌幅": "当日涨跌幅(%)", "主力净流入-净额": "主力净额(亿元)"})
    except:
        return None

north_net = get_north_summary()
if north_net is not None:
    color = "green" if north_net > 0 else "red"
    st.markdown(f"**今日北向资金合计净买额：** :{color}[**{north_net:.2f} 亿元**]")

direction = st.radio("点击切换查看北向资金增减持前十板块：", ["净流入", "净流出"], horizontal=True)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown(f"#### 📈 北向资金{direction}排名")
    board_df = get_north_board_flow(direction)
    if board_df is not None:
        st.dataframe(board_df, use_container_width=True, hide_index=True)
    else:
        st.info("北向板块明细数据暂不可用。")

with col_b:
    st.markdown("#### 💵 行业主力资金净额排行")
    main_df = get_sector_main_flow()
    if main_df is not None:
        st.dataframe(main_df, use_container_width=True, hide_index=True)
    else:
        st.info("主力资金数据暂不可用。")

# 3. 中线趋势与短期题材定性
st.subheader("🔥 中期趋势与短期题材定性")
@st.cache_data(ttl=1800)
def get_sector_trend_analysis():
    try:
        df = ak.stock_board_industry_name_em()
        df = df.sort_values(by="涨跌幅", ascending=False).head(15)
        def tag(row):
            chg = float(row.get("涨跌幅", 0) or 0)
            if chg >= 2.5: return "⚡ 短期题材 / 资金脉冲"
            elif 0.5 <= chg < 2.5: return "📈 中线趋势 / 持续吸金"
            else: return "⏳ 周期波段 / 暂观察"
        df["定性"] = df.apply(tag, axis=1)
        cols = ["板块名称", "涨跌幅", "定性"]
        show_cols = [c for c in cols if c in df.columns]
        return df[show_cols].rename(columns={"涨跌幅": "当日涨跌幅(%)"})
    except:
        return None

trend_df = get_sector_trend_analysis()
if trend_df is not None:
    st.dataframe(trend_df, use_container_width=True, hide_index=True)
    st.caption("提示：单日大涨多为短期题材脉冲；涨幅适中且资金连续流入更具中线趋势特征。")

# 4. 自选基金 T+1 判断
st.subheader("💰 自选基金每日判断 (T+1 规则适配)")
fund_codes = st.text_input("输入基金代码 (逗号分隔)", "110011,161725")

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
        st.caption("场外基金按当日净值确认，建议结合 5 日与 10 日板块资金趋势判断，避免单日追高。")
    else:
        st.info("未能获取基金净值数据，请核对代码。")
