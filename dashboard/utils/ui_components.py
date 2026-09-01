"""
[通用工具与组件层] 通用 UI 组件模块
=============================
封装可复用的 Streamlit UI 组件，所有组件为无状态纯函数。

职责边界：
- 仅负责 UI 渲染，不包含任何业务逻辑
- 仅通过参数接收数据，不直接读取全局状态
- 可被任意页面调用
"""

import streamlit as st
import pandas as pd


# ---------- 指标卡片 ----------

def metric_card(label: str, value, delta: str = None, help_text: str = None) -> None:
    """
    渲染一个指标卡片。

    参数：
        label: 指标名称（如"总记录数"）
        value: 指标数值
        delta: 变化量描述（可选）
        help_text: 悬浮提示（可选）
    """
    if help_text:
        st.metric(label=label, value=value, delta=delta, help=help_text)
    else:
        st.metric(label=label, value=value, delta=delta)


# ---------- 确认弹窗 ----------

def confirm_dialog(key: str, message: str = "确认执行此操作吗？") -> bool:
    """
    渲染一个二次确认组件（checkbox + 按钮组合）。

    参数：
        key: 唯一标识，避免多组件冲突
        message: 确认提示文字

    返回：
        bool — True 表示用户已确认
    """
    confirmed = st.checkbox(f"⚠️ {message}", key=f"confirm_{key}")
    return confirmed


# ---------- 状态徽章 ----------

def status_badge(status: str) -> None:
    """
    根据状态文字渲染不同颜色的徽章。

    参数：
        status: 状态文字（"成功" / "失败" / "运行中" / "待处理" 等）
    """
    color_map = {
        "成功": "green",
        "失败": "red",
        "运行中": "blue",
        "待处理": "orange",
        "已取消": "gray",
    }
    color = color_map.get(status, "gray")
    st.markdown(
        f'<span style="'
        f'display:inline-block;padding:2px 10px;border-radius:10px;'
        f'background:{color};color:white;font-size:13px;'
        f'">{status}</span>',
        unsafe_allow_html=True,
    )


# ---------- 数据表格 ----------

def data_table(df: pd.DataFrame, key: str = "data_table") -> None:
    """
    渲染可排序的数据表格。

    参数：
        df: 要展示的 DataFrame
        key: 组件唯一标识
    """
    if df.empty:
        st.info("暂无数据")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key=key,
    )


# ---------- 页面加载提示 ----------

def page_header(title: str, icon: str = "") -> None:
    """
    渲染页面标题。

    参数：
        title: 页面标题文字
        icon: 标题图标（emoji）
    """
    if icon:
        st.header(f"{icon} {title}")
    else:
        st.header(title)
    st.divider()


# ---------- 空状态占位 ----------

def empty_state(message: str = "暂无数据") -> None:
    """渲染空状态提示。"""
    st.info(f"📭 {message}")
