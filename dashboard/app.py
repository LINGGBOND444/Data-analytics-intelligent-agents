"""
[视图层] Streamlit 管理面板 — 主入口
================================
职责：侧边栏导航 + 全局状态初始化 + 页面路由

架构层级归属：
- 视图层 — 仅负责 UI 渲染与导航，不包含业务逻辑
- 调用 services/agent_service.py 初始化全局任务状态
- 调用 dao/db.py 检查数据库连接状态
"""

import sys
import os

# 将 dashboard/ 和 backend/ 加入搜索路径
_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(os.path.dirname(_DASHBOARD_DIR), "backend")
sys.path.insert(0, _DASHBOARD_DIR)   # dashboard 内部模块（services, dao, utils）
sys.path.insert(0, _BACKEND_DIR)     # 后端模块（src）

import streamlit as st

# ---------- 页面配置（必须放在最前面） ----------
st.set_page_config(
    page_title="销售数据分析智能体 — 管理面板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- 导入服务层 ----------
from services.agent_service import init_session_state, get_agent_status
from dao.db import get_db


def main() -> None:
    """主入口：初始化状态 + 渲染侧边栏 + 路由页面。"""

    # ============================================
    # 1. 全局状态初始化（状态管理层约定）
    # ============================================
    init_session_state()

    # 数据库连接状态（全局状态，命名空间 global_db_）
    if "global_db_connected" not in st.session_state:
        try:
            db = get_db()
            st.session_state["global_db_connected"] = db.test_connection()
        except Exception:
            st.session_state["global_db_connected"] = False

    # ============================================
    # 2. 侧边栏导航（视图层）
    # ============================================
    with st.sidebar:
        st.title("📊 管理面板")
        st.caption("销售数据分析智能体 v1.0")

        st.divider()

        # 数据库状态指示器
        if st.session_state["global_db_connected"]:
            st.success("🟢 数据库已连接")
        else:
            st.error("🔴 数据库未连接")
            st.caption("请检查 .env 配置并重启面板")

        st.divider()

        # 智能体任务状态
        agent_status = get_agent_status()
        if agent_status["running"]:
            st.warning(f"⏳ 任务运行中：{agent_status['progress']}")
        elif agent_status["error"]:
            st.error(f"❌ 上次任务失败")
        elif agent_status["result"]:
            st.success("✅ 上次任务完成")

        st.divider()

        # 导航说明
        st.caption(
            "页面导航：\n"
            "• 📊 数据概览 — 核心指标与图表\n"
            "• 🤖 任务控制 — 启动智能体分析\n"
            "• 📋 数据管理 — 数据增删改查\n"
            "• 📋 运行日志 — 历史执行记录"
        )

        st.divider()
        st.caption("---")
        st.caption(f"数据源：{'MySQL' if st.session_state['global_db_connected'] else '未连接'}")

    # ============================================
    # 3. 页面路由（视图层）
    # ============================================
    # Streamlit 会自动根据 pages/ 目录下的文件名渲染页面
    # 当前文件 (app.py) 即为首页（数据概览）

    st.title("📊 数据概览看板")
    st.caption("销售数据核心指标一览")

    # 检查数据库连接
    if not st.session_state["global_db_connected"]:
        st.warning(
            "⚠️ 数据库未连接，无法加载数据。\n\n"
            "请按以下步骤排查：\n"
            "1. 确认项目目录下有 `.env` 文件（复制 `.env.example` 并填入真实配置）\n"
            "2. 确认 MySQL 服务已启动\n"
            "3. 确认 `.env` 中的数据库地址、端口、用户名、密码正确\n"
            "4. 重启面板"
        )
        return

    # 导入并渲染概览页内容
    _render_dashboard()


def _render_dashboard() -> None:
    """
    渲染数据概览页面内容。

    此函数承载概览页的全部视图渲染逻辑：
    - 调用 services/data_service.py 获取数据
    - 渲染指标卡片 + 图表
    - 处理刷新交互
    """
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd
    from datetime import datetime

    from services.data_service import (
        get_dashboard_stats,
        get_trend_data,
        get_category_distribution,
        get_daily_summary,
    )
    from utils.ui_components import metric_card, empty_state, page_header
    from utils.common import safe_get

    # ---------- 页面级状态初始化 ----------
    if "page_dashboard_last_refresh" not in st.session_state:
        st.session_state["page_dashboard_last_refresh"] = None

    # ---------- 刷新按钮 ----------
    col_title, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("🔄 刷新数据", use_container_width=True):
            st.session_state["page_dashboard_last_refresh"] = datetime.now().strftime(
                "%H:%M:%S"
            )
            st.rerun()

    last_refresh = st.session_state["page_dashboard_last_refresh"]
    if last_refresh:
        st.caption(f"上次刷新：{last_refresh}")

    st.divider()

    # ============================================
    # 一、核心指标卡片
    # ============================================
    st.subheader("核心指标")

    success, stats = get_dashboard_stats()
    if not success:
        st.error(stats)
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "总记录数",
            safe_get(stats, "total_records", 0),
            help_text="数据库中所有业务记录的总数",
        )

    with col2:
        metric_card(
            "今日新增",
            safe_get(stats, "today_records", 0),
            help_text=f"今日（{datetime.now().strftime('%Y-%m-%d')}）新增的记录数",
        )

    with col3:
        metric_card(
            "产品种类",
            safe_get(stats, "unique_products", 0),
            help_text="数据库中包含的产品种类数",
        )

    with col4:
        low_stock = safe_get(stats, "low_stock", 0)
        metric_card(
            "库存紧张",
            low_stock,
            delta=f"⚠️ {low_stock}" if low_stock > 0 else None,
            help_text="当前库存低于阈值的记录数",
        )

    st.divider()

    # ============================================
    # 二、趋势 + 分类图表
    # ============================================
    col_left, col_right = st.columns(2)

    # --- 左：近 7 天趋势折线图 ---
    with col_left:
        st.subheader("近 7 天数据趋势")
        success, trend_data = get_trend_data(days=7)
        if success and trend_data:
            df_trend = pd.DataFrame(trend_data)
            fig = px.line(
                df_trend,
                x="date",
                y="record_count",
                markers=True,
                labels={"date": "日期", "record_count": "记录数"},
            )
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title=None,
                yaxis_title="记录数",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            empty_state("暂无趋势数据")

    # --- 右：分类占比饼图 ---
    with col_right:
        st.subheader("数据分类占比")
        success, cat_data = get_category_distribution()
        if success and cat_data:
            df_cat = pd.DataFrame(cat_data)
            fig = px.pie(
                df_cat,
                names="category",
                values="value",
            )
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            empty_state("暂无分类数据")

    # ============================================
    # 三、每日数据明细表
    # ============================================
    st.divider()
    st.subheader("每日数据明细")

    success, daily_data = get_daily_summary(days=14)
    if success and daily_data:
        df_daily = pd.DataFrame(daily_data)
        # 格式化日期列
        if "date" in df_daily.columns:
            df_daily["date"] = pd.to_datetime(df_daily["date"]).dt.strftime("%Y-%m-%d")

        st.dataframe(
            df_daily,
            column_config={
                "date": st.column_config.TextColumn("日期", width="small"),
                "total_volume": st.column_config.NumberColumn("总销量", format="%.0f"),
                "total_amount": st.column_config.NumberColumn("总销售额（元）", format="%.2f"),
                "product_count": st.column_config.NumberColumn("产品数", format="%d"),
                "avg_price": st.column_config.NumberColumn("均价（元）", format="%.2f"),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        empty_state("暂无每日数据")

    st.divider()
    st.caption("*数据概览看板 — 指标与图表均为实时查询结果")


if __name__ == "__main__":
    main()
else:
    # 作为 Streamlit 多页面应用的一部分被加载时调用
    main()
