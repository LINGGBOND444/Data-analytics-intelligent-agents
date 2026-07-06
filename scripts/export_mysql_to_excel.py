"""
MySQL → Excel 导出脚本
======================
从 MySQL 数据库读取销售数据，导出为 Excel 文件放到 data/ 目录。

用法：
    # 导出昨天的数据（默认）
    python scripts/export_mysql_to_excel.py

    # 导出指定日期的数据
    python scripts/export_mysql_to_excel.py 2026-07-06

    # 在代码中调用
    from scripts.export_mysql_to_excel import export_to_excel
    export_to_excel(config, "2026-07-06")

导出的 Excel 格式和现有 data/ 目录中的文件完全一致（中文列名），
可以直接被现有的分析管线读取。
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

import pandas as pd
import pymysql

logger = logging.getLogger(__name__)

# MySQL 英文列名 → Excel 中文列名的映射
COLUMN_MAP = {
    "date": "日期",
    "product": "产品名称",
    "volume": "销售量",
    "amount": "销售额",
    "price": "单价",
    "stock": "库存",
}

# Excel 列顺序（确保和现有格式一致）
COLUMN_ORDER = ["日期", "产品名称", "销售量", "销售额", "单价", "库存"]


def _get_project_root() -> str:
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_config() -> dict:
    """加载 config.json"""
    config_path = os.path.join(_get_project_root(), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_mysql_connection(mysql_cfg: dict) -> pymysql.Connection:
    """
    建立 MySQL 连接。

    参数：
        mysql_cfg: config.json 中 "数据源" → "MySQL" 的配置

    返回：
        pymysql 数据库连接对象
    """
    return pymysql.connect(
        host=mysql_cfg.get("主机", "localhost"),
        port=mysql_cfg.get("端口", 3306),
        user=mysql_cfg.get("用户名", "root"),
        password=mysql_cfg.get("密码", ""),
        database=mysql_cfg.get("数据库名", "sales"),
        charset="utf8mb4",
        connect_timeout=mysql_cfg.get("连接超时秒", 10),
    )


def _query_date(conn: pymysql.Connection, table_name: str, date_str: str) -> pd.DataFrame:
    """
    从 MySQL 查询指定日期的销售数据。

    参数：
        conn: 数据库连接
        table_name: 表名
        date_str: 日期字符串 YYYY-MM-DD

    返回：
        DataFrame（英文列名）
    """
    sql = f"SELECT date, product, volume, amount, price, stock FROM `{table_name}` WHERE date = %(date)s"
    df = pd.read_sql(sql, conn, params={"date": date_str})

    if df.empty:
        logger.warning(f"MySQL 中没有 {date_str} 的数据")

    return df


def _df_to_excel(df: pd.DataFrame, data_dir: str, date_str: str) -> str:
    """
    将 DataFrame 保存为 Excel 文件。

    参数：
        df: 数据（英文列名）
        data_dir: data/ 目录路径
        date_str: 日期字符串

    返回：
        保存的文件路径
    """
    if df.empty:
        return ""

    # 英文列名 → 中文列名
    df = df.rename(columns=COLUMN_MAP)

    # 只保留需要的列，按固定顺序排列
    available_cols = [c for c in COLUMN_ORDER if c in df.columns]
    df = df[available_cols]

    # 格式化日期列
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")

    # 保存
    os.makedirs(data_dir, exist_ok=True)
    filename = f"销售数据_{date_str}.xlsx"
    filepath = os.path.join(data_dir, filename)

    df.to_excel(filepath, index=False, engine="openpyxl")
    logger.info(f"✓ 已导出：{filename}（{len(df)} 条记录）")

    return filepath


def export_to_excel(config: dict, target_date: str) -> tuple:
    """
    从 MySQL 导出当天和前一天的数据为 Excel。

    这是供 main.py 调用的主函数。

    参数：
        config: 配置字典（从 config.json 加载）
        target_date: 目标日期 YYYY-MM-DD（通常是昨天）

    返回：
        (today_file, prev_file) 两个 Excel 文件路径的元组
    """
    mysql_cfg = config["数据源"]["MySQL"]
    table_name = mysql_cfg.get("表名", "daily_sales")

    # data/ 目录
    data_dir = os.path.join(_get_project_root(), "data")

    # 前一天日期
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    prev_date = (target_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info(f"正在从 MySQL 导出数据...")
    logger.info(f"  主机：{mysql_cfg.get('主机', 'localhost')}:{mysql_cfg.get('端口', 3306)}")
    logger.info(f"  数据库：{mysql_cfg.get('数据库名', 'sales')} / 表：{table_name}")
    logger.info(f"  目标日期：{target_date}  |  前一天：{prev_date}")

    try:
        conn = _get_mysql_connection(mysql_cfg)

        # 导出当天数据
        df_today = _query_date(conn, table_name, target_date)
        today_file = _df_to_excel(df_today, data_dir, target_date)

        # 导出前一天数据（异常检测需要它做环比）
        df_prev = _query_date(conn, table_name, prev_date)
        prev_file = _df_to_excel(df_prev, data_dir, prev_date)

        conn.close()

        if not today_file and not prev_file:
            logger.warning("MySQL 中没有找到任何数据，请检查日期和表内容")

        return today_file, prev_file

    except pymysql.err.OperationalError as e:
        logger.error(f"MySQL 连接失败：{e}")
        logger.error("请检查：1) MySQL 服务是否启动  2) 主机/端口/用户名/密码是否正确")
        return "", ""

    except Exception as e:
        logger.error(f"导出过程出错：{e}")
        return "", ""


# ========== 命令行入口 ==========
if __name__ == "__main__":
    # 设置日志（命令行运行时可以看到详细信息）
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # 获取目标日期
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        # 默认：昨天
        target = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"{'=' * 50}")
    print(f"  MySQL → Excel 数据导出")
    print(f"{'=' * 50}")

    cfg = _load_config()

    # 检查配置的数据源类型
    source_type = cfg.get("数据源", {}).get("类型", "excel")
    if source_type != "mysql":
        print(f"⚠️  当前数据源类型是 '{source_type}'，不是 'mysql'")
        print(f"  如果你确实想从 MySQL 导出，请先将 config.json 中")
        print(f"  '数据源' → '类型' 改为 'mysql'")
        print()
        # 仍然继续执行，因为用户可能就是想测试导出

    today_path, prev_path = export_to_excel(cfg, target)

    print(f"{'=' * 50}")
    if today_path or prev_path:
        print(f"  导出完成！")
        if today_path:
            print(f"  当天数据：{today_path}")
        if prev_path:
            print(f"  前一天数据：{prev_path}")
        print(f"")
        print(f"  接下来可以运行：python main.py")
    else:
        print(f"  导出失败，请检查上面的错误信息")
        print(f"  常见原因：")
        print(f"    1. MySQL 服务未启动")
        print(f"    2. config.json 中连接信息不正确")
        print(f"    3. 数据库中还没有 {target} 的数据")
    print(f"{'=' * 50}")
