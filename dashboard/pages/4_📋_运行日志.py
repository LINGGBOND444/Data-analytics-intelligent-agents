"""
[视图层] 运行日志页面
====================
职责：展示最近执行日志 + 状态/日期筛选

架构层级归属：
- 视图层 — 仅负责 UI 渲染与用户交互承接
- 调用 services/data_service.py 查询日志
- 所有状态使用 page_logs_ 前缀
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ---------- 导入服务层 ----------
from services.agent_service import get_task_history
from services.data_service import get_recent_logs
from utils.ui_components import page_header, empty_state, status_badge
from utils.common import safe_get, fmt_duration, get_date_range

# ============================================
# 页面级状态初始化
# ============================================
if "page_logs_status_filter" not in st.session_state:
    st.session_state["page_logs_status_filter"] = "全部"
if "page_logs_date_from" not in st.session_state:
    st.session_state["page_logs_date_from"] = None
if "page_logs_date_to" not in st.session_state:
    st.session_state["page_logs_date_to"] = None
if "page_logs_source" not in st.session_state:
    st.session_state["page_logs_source"] = "本地记录"


def main() -> None:
    """运行日志页面入口。"""
    page_header("运行日志", "📋")

    # ---------- 数据源切换 ----------
    source = st.radio(
        "日志来源",
        options=["本地记录", "数据库（MySQL）"],
        horizontal=True,
        key="log_source_radio",
        help="本地记录：本次会话中的执行历史\n数据库：MySQL 日志表中的持久化记录",
    )
    st.session_state["page_logs_source"] = source

    # ---------- 筛选条件 ----------
    st.subheader("筛选条件")

    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.selectbox(
            "执行状态",
            options=["全部", "成功", "失败"],
            key="log_status_select",
        )
        st.session_state["page_logs_status_filter"] = status_filter

    with col2:
        date_from = st.date_input(
            "起始日期",
            value=None,
            key="log_date_from",
        )
        st.session_state["page_logs_date_from"] = (
            date_from.strftime("%Y-%m-%d") if date_from else None
        )

    with col3:
        date_to = st.date_input(
            "截止日期",
            value=None,
            key="log_date_to",
        )
        st.session_state["page_logs_date_to"] = (
            date_to.strftime("%Y-%m-%d") if date_to else None
        )

    if st.button("🔍 查询日志", type="primary"):
        st.rerun()

    st.divider()

    # ---------- 获取日志数据 ----------
    if source == "本地记录":
        _render_local_logs()
    else:
        _render_db_logs()


def _render_local_logs() -> None:
    """渲染本地 session_state 中的日志。"""
    success, logs = get_task_history(limit=50)
    if not success:
        st.error(logs)
        return

    if not logs:
        empty_state("暂无本地执行记录，启动一次智能体任务后将在此显示")
        return

    # 筛选
    status_filter = st.session_state["page_logs_status_filter"]
    if status_filter != "全部":
        logs = [log for log in logs if log.get("状态") == status_filter]

    if not logs:
        empty_state(f"没有状态为「{status_filter}」的记录")
        return

    # 渲染表格
    st.caption(f"共 {len(logs)} 条记录")

    for log in reversed(logs):
        status = safe_get(log, "状态", "-")
        time_str = safe_get(log, "时间", "-")
        task_name = safe_get(log, "任务名称", "-")
        duration = safe_get(log, "耗时", "-")
        detail = safe_get(log, "详情", "-")

        with st.expander(f"{time_str} — {task_name} — {status}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**状态**：")
                if status == "成功":
                    st.success(status)
                elif status == "失败":
                    st.error(status)
                else:
                    st.info(status)
            with col2:
                st.write(f"**耗时**：{duration}")
            st.write(f"**详情**：{detail}")


def _render_db_logs() -> None:
    """渲染数据库中的日志记录。"""
    status_filter = st.session_state["page_logs_status_filter"]
    date_from = st.session_state["page_logs_date_from"]
    date_to = st.session_state["page_logs_date_to"]

    status_param = None if status_filter == "全部" else status_filter

    success, logs = get_recent_logs(
        status=status_param,
        date_from=date_from,
        date_to=date_to,
        limit=50,
    )

    if not success:
        st.warning(
            f"{logs}\n\n"
            "> **提示**：数据库日志功能需要在 MySQL 中创建 `agent_logs` 表。\n"
            "> 当前版本日志默认保存在本地记录中，无需数据库日志表也能查看。"
        )
        return

    if not logs:
        empty_state("暂无符合筛选条件的日志记录")
        return

    # 渲染表格
    st.caption(f"共 {len(logs)} 条记录")

    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
else:
    main()
