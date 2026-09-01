"""
[通用工具与组件层] 通用工具函数模块
============================
提供项目通用的纯函数工具，不依赖业务状态与业务表结构。

职责边界：
- 仅包含无状态纯函数，可被任意上层调用
- 不包含任何业务逻辑，不依赖业务表或字段
- 不直接操作数据库
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Any


# ---------- 日期工具 ----------

def fmt_date(date_value: Any, fmt: str = "%Y-%m-%d") -> str:
    """
    将各种日期格式统一转换为字符串。

    参数：
        date_value: datetime / date / str
        fmt: 目标格式

    返回：
        格式化后的日期字符串，转换失败返回原始值
    """
    if date_value is None:
        return ""
    if isinstance(date_value, datetime):
        return date_value.strftime(fmt)
    if hasattr(date_value, "strftime"):
        return date_value.strftime(fmt)
    return str(date_value)


def get_date_range(days: int = 7) -> tuple[str, str]:
    """
    获取最近 N 天的日期范围。

    参数：
        days: 天数

    返回：
        (date_from, date_to) 格式 YYYY-MM-DD
    """
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    return date_from, date_to


# ---------- 数据导出 ----------

def df_to_csv_download(df, filename: str = "export.csv") -> bytes:
    """
    将对象列表/DataFrame 转换为 CSV 字节串。

    参数：
        df: list[dict] 或 pandas DataFrame
        filename: 文件名（仅用于生成时的注释，实际下载文件名由调用方指定）

    返回：
        bytes — UTF-8 BOM 编码的 CSV 内容
    """
    import pandas as pd

    if isinstance(df, list):
        df = pd.DataFrame(df)

    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return output.getvalue().encode("utf-8-sig")


# ---------- 格式化工具 ----------

def fmt_number(value: Any, decimals: int = 2) -> str:
    """安全地将数值格式化为千分位字符串。"""
    try:
        num = float(value)
        if num == int(num):
            return f"{int(num):,}"
        return f"{num:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value) if value is not None else "-"


def fmt_duration(seconds: float) -> str:
    """
    将秒数格式化为可读的耗时字符串。

    参数：
        seconds: 秒数

    返回：
        如 "2分30秒" / "0.5秒"
    """
    if seconds < 1:
        return f"{seconds:.1f}秒"
    if seconds < 60:
        return f"{seconds:.0f}秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}分{secs}秒"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}小时{mins}分"


# ---------- 安全取值 ----------

def safe_get(data: dict, key: str, default: Any = "-") -> Any:
    """
    安全地从字典中取值，避免 KeyError。

    参数：
        data: 字典
        key: 键名
        default: 键不存在时的默认值
    """
    return data.get(key, default) if isinstance(data, dict) else default
