"""
[业务服务层] 智能体调用服务模块
===========================
封装对现有智能体模块的调用，管理后台异步执行与状态。

职责边界：
- 通过 threading 实现后台异步执行，禁止阻塞 Streamlit 主线程
- 统一包装执行结果与异常，返回标准化 (True/False, 信息) 格式
- 通过 st.session_state 存储任务状态，遵循全局状态命名规则
- 严格禁止：直接包含UI渲染逻辑、直接操作数据库连接
"""

import threading
import time
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ============================================
# 全局状态键名（遵循 global_task_ 命名空间）
# ============================================
GLOBAL_TASK_RUNNING = "global_task_running"
GLOBAL_TASK_START_TIME = "global_task_start_time"
GLOBAL_TASK_END_TIME = "global_task_end_time"
GLOBAL_TASK_PROGRESS = "global_task_progress"
GLOBAL_TASK_RESULT = "global_task_result"
GLOBAL_TASK_ERROR = "global_task_error"
GLOBAL_TASK_HISTORY = "global_task_history"


# ============================================
# 智能体导入占位符
# ============================================
# ---- 替换说明 ----
# 将下面的导入路径替换为你的实际智能体模块路径
# 例如：from my_agent.core import run_pipeline
# ------------------

# 尝试导入现有智能体模块（如果不可用则置为 None）
try:
    from src.data_fetcher import fetch_sales_data
    from src.anomaly_detector import detect_anomalies
    from src.analyzer import analyze_anomalies
    from src.reporter import generate_report
    from src.notifier import send_notification
    AGENT_IMPORTED = True
except ImportError as e:
    AGENT_IMPORTED = False
    _IMPORT_ERROR = str(e)


# ============================================
# 公开函数（供视图层调用）
# ============================================

def init_session_state() -> None:
    """
    在 app.py 启动时调用，初始化全局任务状态。

    调用位置：app.py 顶部，在所有页面渲染之前。
    如果 session_state 中已有状态则保留（防止重复初始化覆盖运行时状态）。
    """
    import streamlit as st

    defaults = {
        GLOBAL_TASK_RUNNING: False,
        GLOBAL_TASK_START_TIME: None,
        GLOBAL_TASK_END_TIME: None,
        GLOBAL_TASK_PROGRESS: "未启动",
        GLOBAL_TASK_RESULT: None,
        GLOBAL_TASK_ERROR: None,
        GLOBAL_TASK_HISTORY: [],
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_agent_status() -> dict:
    """
    获取当前智能体任务的执行状态。

    返回：
        dict: {
            "running": bool,         是否正在运行
            "start_time": str|None,  启动时间
            "end_time": str|None,    结束时间
            "progress": str,         当前进度描述
            "result": str|None,      执行结果
            "error": str|None,       错误信息
        }
    """
    import streamlit as st

    return {
        "running": st.session_state.get(GLOBAL_TASK_RUNNING, False),
        "start_time": st.session_state.get(GLOBAL_TASK_START_TIME),
        "end_time": st.session_state.get(GLOBAL_TASK_END_TIME),
        "progress": st.session_state.get(GLOBAL_TASK_PROGRESS, "未启动"),
        "result": st.session_state.get(GLOBAL_TASK_RESULT),
        "error": st.session_state.get(GLOBAL_TASK_ERROR),
    }


def start_agent_task(config_params: dict) -> tuple[bool, str]:
    """
    启动智能体后台任务。

    参数：
        config_params: {
            "target_date": str,              目标日期 YYYY-MM-DD（可选，默认昨天）
            "threshold": int,                异常阈值百分比（可选，默认 30）
            "enable_ai": bool,               是否启用 AI 分析（可选，默认 True）
            "enable_notification": bool,     是否启用推送（可选，默认 False）
        }

    返回：
        (True, "任务已启动") 或 (False, "错误原因")

    副作用：
        在 st.session_state 中更新 global_task_* 系列状态
    """
    import streamlit as st

    # 检查是否已在运行
    if st.session_state.get(GLOBAL_TASK_RUNNING, False):
        return False, "当前有任务正在执行中，请等待完成后再启动"

    # 检查智能体是否可用
    if not AGENT_IMPORTED:
        return False, f"智能体模块导入失败：{_IMPORT_ERROR}"

    # 重置状态
    st.session_state[GLOBAL_TASK_RUNNING] = True
    st.session_state[GLOBAL_TASK_START_TIME] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state[GLOBAL_TASK_END_TIME] = None
    st.session_state[GLOBAL_TASK_PROGRESS] = "正在初始化..."
    st.session_state[GLOBAL_TASK_RESULT] = None
    st.session_state[GLOBAL_TASK_ERROR] = None

    # 启动后台线程
    thread = threading.Thread(
        target=_run_agent_pipeline,
        args=(config_params,),
        daemon=True,
    )
    thread.start()

    return True, "任务已启动，正在后台执行..."


def get_task_history(limit: int = 50) -> tuple[bool, list]:
    """
    获取本地执行历史记录（来自 session_state）。

    参数：
        limit: 返回条数上限

    返回：
        (True, [{...}]) 或 (False, "错误信息")
    """
    import streamlit as st

    history = st.session_state.get(GLOBAL_TASK_HISTORY, [])
    return True, history[-limit:]


def cancel_agent_task() -> tuple[bool, str]:
    """
    取消当前正在执行的任务。

    注意：仅标记取消，实际线程可能需要完成后才能终止。

    返回：
        (True, "已发送取消信号") 或 (False, "当前无任务运行")
    """
    import streamlit as st

    if not st.session_state.get(GLOBAL_TASK_RUNNING, False):
        return False, "当前没有正在运行的任务"

    st.session_state[GLOBAL_TASK_RUNNING] = False
    st.session_state[GLOBAL_TASK_PROGRESS] = "用户取消"
    st.session_state[GLOBAL_TASK_END_TIME] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return True, "已发送取消信号"


# ============================================
# 私有函数 — 后台任务执行
# ============================================

def _run_agent_pipeline(params: dict) -> None:
    """
    在后台线程中执行完整的智能体分析管线。

    执行流程（同 main.py）：
        数据拉取 → 异常检测 → AI 分析 → 报告生成 → 推送通知
    """
    import streamlit as st
    import json
    import os
    from datetime import datetime, timedelta

    start_time = time.time()

    try:
        # ----- 加载配置 -----
        st.session_state[GLOBAL_TASK_PROGRESS] = "正在加载配置..."

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "backend", "config.json",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 用用户参数覆盖配置
        target_date = params.get(
            "target_date",
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        if "threshold" in params:
            config["异常检测"]["环比阈值_百分比"] = int(params["threshold"])
        if "enable_ai" in params:
            config["AI分析"]["启用"] = bool(params["enable_ai"])

        # ----- 数据拉取 -----
        st.session_state[GLOBAL_TASK_PROGRESS] = "正在拉取销售数据..."
        sales_data = fetch_sales_data(config, target_date)
        if sales_data.empty:
            raise ValueError(f"未找到 {target_date} 的销售数据")

        # ----- 异常检测 -----
        st.session_state[GLOBAL_TASK_PROGRESS] = "正在进行异常检测..."
        anomalies, comparison_date = detect_anomalies(config, sales_data)

        # ----- AI 分析 -----
        analysis_results = []
        if config.get("AI分析", {}).get("启用", True) and not anomalies.empty:
            st.session_state[GLOBAL_TASK_PROGRESS] = "正在进行 AI 归因分析..."
            analysis_results = analyze_anomalies(config, anomalies, sales_data, comparison_date)

        # ----- 报告生成 -----
        st.session_state[GLOBAL_TASK_PROGRESS] = "正在生成分析报告..."
        report_path = generate_report(
            config, sales_data, anomalies, analysis_results, target_date, comparison_date
        )

        # ----- 推送通知 -----
        if params.get("enable_notification", False):
            st.session_state[GLOBAL_TASK_PROGRESS] = "正在推送通知..."
            send_notification(config, report_path, len(anomalies), target_date)

        # ----- 完成 -----
        elapsed = time.time() - start_time
        result_msg = (
            f"✅ 分析完成！\n\n"
            f"- 分析日期：{target_date}\n"
            f"- 产品数量：{len(sales_data)} 个\n"
            f"- 异常数量：{len(anomalies)} 个\n"
            f"- 报告路径：{report_path}\n"
            f"- 总耗时：{elapsed:.1f} 秒"
        )

        st.session_state[GLOBAL_TASK_RESULT] = result_msg
        st.session_state[GLOBAL_TASK_ERROR] = None
        st.session_state[GLOBAL_TASK_PROGRESS] = "执行完成"

        # 记录到历史
        history = st.session_state.get(GLOBAL_TASK_HISTORY, [])
        history.append({
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "任务名称": f"销售分析 - {target_date}",
            "状态": "成功",
            "耗时": f"{elapsed:.1f}秒",
            "详情": f"发现 {len(anomalies)} 个异常",
        })
        st.session_state[GLOBAL_TASK_HISTORY] = history

    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"执行失败：{e}"
        logger.error(error_msg, exc_info=True)

        st.session_state[GLOBAL_TASK_RESULT] = None
        st.session_state[GLOBAL_TASK_ERROR] = error_msg
        st.session_state[GLOBAL_TASK_PROGRESS] = "执行失败"

        # 记录失败历史
        history = st.session_state.get(GLOBAL_TASK_HISTORY, [])
        history.append({
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "任务名称": f"销售分析 - {params.get('target_date', '自动')}",
            "状态": "失败",
            "耗时": f"{elapsed:.1f}秒",
            "详情": error_msg,
        })
        st.session_state[GLOBAL_TASK_HISTORY] = history

    finally:
        st.session_state[GLOBAL_TASK_RUNNING] = False
        st.session_state[GLOBAL_TASK_END_TIME] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
