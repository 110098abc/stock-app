import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(page_title="A股监测", layout="wide")
st.title("📊 我的A股专属看板")
st.caption(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

def get_idx(code):
    try:
        r = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=10)
        r.encoding = "gbk"
        parts = r.text.split("~")
        return float(parts[3])
    except:
        return 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("上证指数", get_idx("sh000001"))
c2.metric("深证成指", get_idx("sz399001"))
c3.metric("恒生指数", get_idx("hkHSI"))
c4.metric("恒生科技", get_idx("hkHSTECH"))

st.info("⚠️ 关键位提醒：上证指数注意 3700 点关口，若失守需警惕由攻转守。")

st.subheader("自选基金每日判断 (演示)")
df_funds = pd.DataFrame({
    "基金名称": ["易方达蓝筹", "招商白酒", "沪深300"],
    "状态": ["持有逻辑维持", "逻辑转弱观察", "持有逻辑维持"]
})
st.dataframe(df_funds, use_container_width=True, hide_index=True)
