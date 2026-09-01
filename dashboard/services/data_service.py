"""
[业务服务层] 业务数据服务模块
=========================
封装数据管理相关业务逻辑，衔接视图层与数据访问层。

职责边界：
- 负责参数校验、业务规则判断、结果加工
- 调用数据访问层（dao/db.py）执行数据库操作
- 返回标准化结果：(True, 数据) 或 (False, 错误信息)
- 严格禁止：直接操作数据库连接、包含UI渲染逻辑、直接被视图层以外的层级调用
"""

import logging
from typing import Any
from datetime import datetime

import pandas as pd

from dao.db import get_db
from utils.common import safe_get

logger = logging.getLogger(__name__)

# ============================================
# 业务数据服务 — 公开函数
# ============================================

# ---------- 概览统计 ----------

def get_dashboard_stats() -> tuple[bool, dict]:
    """
    获取仪表盘核心统计指标。

    返回格式：
        (True, {
            "total_records": int,      总记录数
            "today_records": int,      今日新增数
            "unique_products": int,     产品种类数
            "low_stock": int,           库存紧张记录数
        })
    """
    db = get_db()
    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        total = db.execute_query(
            "SELECT COUNT(*) AS cnt FROM daily_sales"
        )
        today = db.execute_query(
            "SELECT COUNT(*) AS cnt FROM daily_sales WHERE date = %(today)s",
            {"today": today_str},
        )

        unique_products = db.execute_query(
            "SELECT COUNT(DISTINCT product) AS cnt FROM daily_sales"
        )

        low_stock = db.execute_query(
            "SELECT COUNT(*) AS cnt FROM daily_sales WHERE stock < 10 AND date = %(today)s",
            {"today": today_str},
        )

        stats = {
            "total_records": safe_get(total[0], "cnt", 0) if total else 0,
            "today_records": safe_get(today[0], "cnt", 0) if today else 0,
            "unique_products": safe_get(unique_products[0], "cnt", 0) if unique_products else 0,
            "low_stock": safe_get(low_stock[0], "cnt", 0) if low_stock else 0,
        }
        return True, stats

    except Exception as e:
        return False, f"获取概览数据失败：{e}"


# ---------- 趋势图 ----------

def get_trend_data(days: int = 7) -> tuple[bool, list]:
    """
    获取近 N 天每日数据记录数趋势。

    参数：
        days: 统计天数

    返回：
        (True, [
            {"date": "2026-07-01", "record_count": 15},
            ...
        ])
    """
    db = get_db()
    try:
        rows = db.execute_query(
            "SELECT date, COUNT(*) AS record_count "
            "FROM daily_sales "
            "WHERE date >= DATE_SUB(CURDATE(), INTERVAL %(days)s DAY) "
            "GROUP BY date ORDER BY date",
            {"days": days},
        )
        return True, rows if rows else []
    except Exception as e:
        return False, f"获取趋势数据失败：{e}"


# ---------- 分类占比 ----------

def get_category_distribution() -> tuple[bool, list]:
    """
    获取各产品销售额占比。

    返回：
        (True, [
            {"category": "产品A", "value": 100},
            ...
        ])
    """
    db = get_db()
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        rows = db.execute_query(
            "SELECT product AS category, "
            "SUM(amount) AS value "
            "FROM daily_sales "
            "WHERE date = %(today)s "
            "GROUP BY product "
            "ORDER BY value DESC",
            {"today": today_str},
        )
        return True, rows if rows else []
    except Exception as e:
        return False, f"获取分类数据失败：{e}"


# ---------- 每日数据汇总表 ----------

def get_daily_summary(days: int = 14) -> tuple[bool, list]:
    """
    获取近 N 天按日期汇总的数据明细。

    返回：
        (True, [
            {"date": "2026-07-01", "total_volume": 100, "total_amount": 5000,
             "product_count": 5, "avg_price": 50.0},
            ...
        ])
    """
    db = get_db()
    try:
        rows = db.execute_query(
            "SELECT date, "
            "SUM(volume) AS total_volume, "
            "SUM(amount) AS total_amount, "
            "COUNT(DISTINCT product) AS product_count, "
            "ROUND(SUM(amount) / NULLIF(SUM(volume), 0), 2) AS avg_price "
            "FROM daily_sales "
            "WHERE date >= DATE_SUB(CURDATE(), INTERVAL %(days)s DAY) "
            "GROUP BY date "
            "ORDER BY date DESC",
            {"days": days},
        )
        return True, rows if rows else []
    except Exception as e:
        return False, f"获取每日汇总失败：{e}"


# ---------- 产品名称列表 ----------

def get_product_names() -> list[str]:
    """
    获取数据库中所有不重复的产品名称，用于联想输入下拉菜单。

    返回：
        ["红富士苹果", "进口香蕉", ...]
    """
    db = get_db()
    try:
        rows = db.execute_query(
            "SELECT DISTINCT product FROM daily_sales ORDER BY product"
        )
        return [row["product"] for row in rows] if rows else []
    except Exception as e:
        logger.warning(f"获取产品名称列表失败：{e}")
        return []


# ---------- 数据管理 ----------

def query_data(filters: dict, page: int = 1, page_size: int = 20) -> tuple[bool, dict]:
    """
    按条件分页查询业务数据。

    参数：
        filters: {"date_from", "date_to", "product", ...} — 筛选条件
        page: 页码（从 1 开始）
        page_size: 每页条数

    返回：
        (True, {"rows": [...], "total": 100, "page": 1, "page_size": 20})
    """
    db = get_db()

    conditions = ["1=1"]
    params = {}

    if filters.get("date_from"):
        conditions.append("date >= %(date_from)s")
        params["date_from"] = filters["date_from"]
    if filters.get("date_to"):
        conditions.append("date <= %(date_to)s")
        params["date_to"] = filters["date_to"]
    if filters.get("product"):
        conditions.append("product LIKE %(product)s")
        params["product"] = f"%{filters['product']}%"

    where_clause = " AND ".join(conditions)

    try:
        count_result = db.execute_query(
            f"SELECT COUNT(*) AS total FROM daily_sales WHERE {where_clause}",
            params,
        )
        total = safe_get(count_result[0], "total", 0) if count_result else 0

        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        rows = db.execute_query(
            f"SELECT * FROM daily_sales "
            f"WHERE {where_clause} "
            f"ORDER BY id DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s",
            params,
        )

        return True, {
            "rows": rows if rows else [],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except Exception as e:
        return False, f"查询数据失败：{e}"


def insert_data(record: dict) -> tuple[bool, str]:
    """
    新增一条销售数据记录。

    参数：
        record: 要插入的数据字典 {字段名: 值}

    返回：
        (True, "新增成功") 或 (False, "错误信息")
    """
    db = get_db()
    if not record:
        return False, "数据不能为空"

    columns = ", ".join(f"`{k}`" for k in record.keys())
    placeholders = ", ".join(f"%({k})s" for k in record.keys())

    try:
        db.execute_write(
            f"INSERT INTO daily_sales ({columns}) VALUES ({placeholders})",
            record,
        )
        return True, "新增成功"
    except Exception as e:
        return False, f"新增失败：{e}"


def delete_data(record_id: int) -> tuple[bool, str]:
    """
    删除一条销售数据记录。

    参数：
        record_id: 主键 ID

    返回：
        (True, "删除成功") 或 (False, "错误信息")
    """
    db = get_db()
    try:
        affected = db.execute_write(
            "DELETE FROM daily_sales WHERE id = %(id)s",
            {"id": record_id},
        )
        if affected == 0:
            return False, "未找到该记录"
        return True, "删除成功"
    except Exception as e:
        return False, f"删除失败：{e}"


def export_csv(filters: dict) -> tuple[bool, Any]:
    """
    导出查询结果为 CSV 格式。

    参数：
        filters: 筛选条件（同 query_data）

    返回：
        (True, csv_bytes) 或 (False, "错误信息")
    """
    success, result = query_data(filters, page=1, page_size=10000)
    if not success:
        return False, result

    import pandas as pd
    from utils.common import df_to_csv_download

    df = pd.DataFrame(result["rows"])
    if df.empty:
        return False, "没有符合条件的数据可导出"

    csv_bytes = df_to_csv_download(df)
    return True, csv_bytes


# ---------- 日志查询 ----------

def get_recent_logs(
    status: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 50,
) -> tuple[bool, list]:
    """
    查询最近的智能体执行日志。

    注意：需要在 MySQL 中创建 agent_logs 表才能使用此功能。
    日志表结构：id, created_at, status, task_name, detail 等字段。

    参数：
        status: 按状态筛选（"成功" / "失败" / None=全部）
        date_from: 起始日期 YYYY-MM-DD
        date_to: 截止日期 YYYY-MM-DD
        limit: 返回条数上限

    返回：
        (True, [{...}]) 或 (False, "错误信息")
    """
    db = get_db()

    conditions = ["1=1"]
    params = {}

    if status:
        conditions.append("status = %(status)s")
        params["status"] = status
    if date_from:
        conditions.append("created_at >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        conditions.append("created_at <= %(date_to)s")
        params["date_to"] = date_to + " 23:59:59"

    params["limit"] = limit
    where_clause = " AND ".join(conditions)

    try:
        rows = db.execute_query(
            f"SELECT * FROM agent_logs "
            f"WHERE {where_clause} "
            f"ORDER BY created_at DESC "
            f"LIMIT %(limit)s",
            params,
        )
        return True, rows if rows else []
    except Exception as e:
        return False, f"查询日志失败：{e}"
