"""
[视图层] 智能体任务控制页面
=========================
职责：参数表单收集 + 启动任务 + 二次确认 + 实时状态展示

架构层级归属：
- 视图层 — 仅负责 UI 渲染与用户交互承接
- 调用 services/agent_service.py 执行业务操作
- 读写 session_state 中的 global_task_* 状态
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime, timedelta

# ---------- 导入服务层 ----------
from services.agent_service import (
    start_agent_task,
    get_agent_status,
    cancel_agent_task,
    GLOBAL_TASK_RUNNING,
    GLOBAL_TASK_START_TIME,
    GLOBAL_TASK_END_TIME,
    GLOBAL_TASK_PROGRESS,
    GLOBAL_TASK_RESULT,
    GLOBAL_TASK_ERROR,
)

# ---------- 导入通用组件 ----------
from utils.ui_components import confirm_dialog, status_badge, page_header
from utils.common import fmt_duration


# ============================================
# 页面级状态初始化
# ============================================
if "page_task_confirm" not in st.session_state:
    st.session_state["page_task_confirm"] = False
if "page_task_params" not in st.session_state:
    st.session_state["page_task_params"] = {}


def main() -> None:
    """任务控制页面入口。"""
    page_header("智能体任务控制", "🤖")

    # ---------- 任务状态区域 ----------
    _render_task_status()

    st.divider()

    # ---------- 参数配置区域 ----------
    st.subheader("任务参数配置")

    with st.form(key="task_params_form"):
        col1, col2 = st.columns(2)

        with col1:
            target_date = st.date_input(
                "目标分析日期",
                value=datetime.now() - timedelta(days=1),
                help="分析哪一天的销售数据（默认昨天）",
                key="form_target_date",
            )

            threshold = st.slider(
                "异常阈值 (%)",
                min_value=10,
                max_value=50,
                value=30,
                step=5,
                help="销量涨跌超过此百分比即标记为异常",
                key="form_threshold",
            )

        with col2:
            enable_ai = st.checkbox(
                "启用 AI 归因分析",
                value=True,
                help="调用 DeepSeek API 进行智能分析（耗时较长）",
                key="form_enable_ai",
            )

            enable_notification = st.checkbox(
                "启用钉钉推送",
                value=False,
                help="分析完成后自动推送到钉钉群",
                key="form_enable_notification",
            )

        st.divider()

        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            submitted = st.form_submit_button(
                "🚀 启动执行",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.get(GLOBAL_TASK_RUNNING, False),
            )
        with col_btn2:
            cancel_clicked = st.form_submit_button(
                "⏹️ 取消任务",
                use_container_width=True,
                disabled=not st.session_state.get(GLOBAL_TASK_RUNNING, False),
            )

        if submitted:
            st.session_state["page_task_params"] = {
                "target_date": target_date.strftime("%Y-%m-%d"),
                "threshold": threshold,
                "enable_ai": enable_ai,
                "enable_notification": enable_notification,
            }
            st.session_state["page_task_confirm"] = True
            st.rerun()

        if cancel_clicked:
            success, msg = cancel_agent_task()
            if success:
                st.warning(msg)
            else:
                st.info(msg)
            st.rerun()

    # ---------- 二次确认弹窗 ----------
    if st.session_state.get("page_task_confirm", False):
        st.divider()
        st.warning("### ⚠️ 确认执行")

        params = st.session_state["page_task_params"]
        st.write("即将启动智能体任务，参数如下：")
        st.write(f"- 分析日期：**{params['target_date']}**")
        st.write(f"- 异常阈值：**{params['threshold']}%**")
        st.write(f"- AI 分析：**{'启用' if params['enable_ai'] else '禁用'}**")
        st.write(f"- 推送通知：**{'启用' if params['enable_notification'] else '禁用'}**")

        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("✅ 确认启动", type="primary", use_container_width=True):
                st.session_state["page_task_confirm"] = False
                success, msg = start_agent_task(params)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
                st.rerun()
        with col_cancel:
            if st.button("❌ 取消", use_container_width=True):
                st.session_state["page_task_confirm"] = False
                st.rerun()


def _render_task_status() -> None:
    """渲染当前任务执行状态区域。"""
    st.subheader("任务状态")

    status = get_agent_status()

    col1, col2, col3 = st.columns(3)

    with col1:
        if status["running"]:
            st.markdown("**运行状态** ⏳ 运行中")
        elif status["error"]:
            st.markdown("**运行状态** ❌ 失败")
        elif status["result"]:
            st.markdown("**运行状态** ✅ 完成")
        else:
            st.markdown("**运行状态** ⚪ 空闲")

    with col2:
        st.markdown(f"**当前进度**：{status['progress']}")

    with col3:
        if status["start_time"]:
            st.markdown(f"**启动时间**：{status['start_time']}")
        if status["end_time"]:
            st.markdown(f"**结束时间**：{status['end_time']}")

    # 实时进度条
    if status["running"]:
        st.progress(0.5, text=f"执行中：{status['progress']}")
    elif status["result"]:
        st.success(status["result"])
    elif status["error"]:
        st.error(status["error"])

    # 自动刷新：正在运行中时每 2 秒刷新状态
    if status["running"]:
        st.caption("⏳ 任务正在后台执行，页面会自动刷新状态...")
        st.rerun() if not st.session_state.get("_just_reran") else None
        st.session_state["_just_reran"] = True
        import time
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
else:
    main()
