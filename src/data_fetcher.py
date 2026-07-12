"""
数据拉取模块
============
从 Excel 文件或 MySQL 数据库读取销售数据。

Excel 模式（优先）：
  - 自动从 data/ 目录找最新的 Excel 文件
  - 支持 .xlsx 和 .csv 格式

MySQL 模式：
  - 通过 pymysql 连接数据库
  - 在 config.json 中配置连接信息
"""

import os
import glob
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# 期望的列名（中文）
EXPECTED_COLUMNS = ["日期", "产品名称", "销售量", "销售额", "单价", "库存"]
OPTIONAL_COLUMNS = ["日进货量"]  # 有则检测库存不足，无则跳过，不报错

# 也支持英文列名（自动映射）
COLUMN_ALIASES = {
    "date": "日期",
    "product": "产品名称",
    "product_name": "产品名称",
    "name": "产品名称",
    "sales_volume": "销售量",
    "volume": "销售量",
    "quantity": "销售量",
    "sales_amount": "销售额",
    "amount": "销售额",
    "revenue": "销售额",
    "price": "单价",
    "unit_price": "单价",
    "stock": "库存",
    "inventory": "库存",
    "restock": "日进货量",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将英文列名统一映射为中文列名"""
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col_lower]
    if rename_map:
        df = df.rename(columns=rename_map)
        logger.info(f"列名映射：{rename_map}")
    return df


def _validate_columns(df: pd.DataFrame):
    """检查数据是否包含必要的列（可选列缺失不报错）"""
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"数据缺少必要列：{missing}\n"
            f"当前列名：{list(df.columns)}\n"
            f"期望列名（中文）：{EXPECTED_COLUMNS}\n"
            f"也支持英文列名：{list(COLUMN_ALIASES.keys())}"
        )
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            logger.info(f"可选列「{col}」不存在，相关检测将跳过")


def fetch_from_excel(config: dict, target_date: str) -> pd.DataFrame:
    """
    从 Excel 文件读取数据。

    逻辑：
    1. 扫描 data/ 目录下的 .xlsx / .csv 文件
    2. 优先选文件名包含目标日期的文件
    3. 否则选最新修改的文件
    4. 读取后筛选目标日期的数据
    """
    data_dir = config["数据源"].get("Excel文件目录", "./data")

    # 解决相对路径
    if data_dir.startswith("./"):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), data_dir[2:])

    os.makedirs(data_dir, exist_ok=True)

    # 查找 Excel 文件
    patterns = [f"{data_dir}/*.xlsx", f"{data_dir}/*.csv"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"在 {data_dir} 目录下没有找到 Excel 文件（.xlsx 或 .csv）\n"
            f"请将销售数据文件放入该目录后重试。"
        )

    # 优先匹配目标日期的文件
    date_short = target_date.replace("-", "")  # 2026-07-05 → 20260705
    matched = [f for f in files if target_date in f or date_short in f]

    if matched:
        file_path = matched[0]
        logger.info(f"找到匹配日期的文件：{os.path.basename(file_path)}")
    else:
        # 取最新修改的文件
        file_path = max(files, key=os.path.getmtime)
        logger.info(f"未找到匹配日期的文件，使用最新文件：{os.path.basename(file_path)}")

    # 读取文件
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path, encoding="utf-8-sig")
    else:
        df = pd.read_excel(file_path, engine="openpyxl")

    logger.info(f"读取到 {len(df)} 行数据，列名：{list(df.columns)}")

    # 规范化列名
    df = _normalize_columns(df)
    _validate_columns(df)

    # 筛选目标日期
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
    df = df[df["日期"] == target_date].copy()

    if df.empty:
        logger.warning(f"文件中没有找到 {target_date} 的数据")
    else:
        logger.info(f"筛选出 {target_date} 的数据：{len(df)} 行")

    return df


def fetch_from_mysql(config: dict, target_date: str) -> pd.DataFrame:
    """从 MySQL 数据库读取数据"""
    import pymysql

    mysql_cfg = config["数据源"]["MySQL"]
    conn = pymysql.connect(
        host=mysql_cfg["主机"],
        port=mysql_cfg["端口"],
        user=mysql_cfg["用户名"],
        password=mysql_cfg["密码"],
        database=mysql_cfg["数据库名"],
        charset="utf8mb4",
    )

    table = mysql_cfg["表名"]
    sql = """
    SELECT
        date AS 日期,
        product AS 产品名称,
        volume AS 销售量,
        amount AS 销售额,
        price AS 单价,
        stock AS 库存,
        restock AS 日进货量
    FROM daily_sales
    WHERE date = %(date)s
    """
    df = pd.read_sql(sql, conn, params={"date": target_date})

    # 也尝试英文日期列名
    if df.empty:
        sql = f"SELECT * FROM `{table}` WHERE `date` = %(date)s"
        df = pd.read_sql(sql, conn, params={"date": target_date})

    conn.close()

    df = _normalize_columns(df)
    _validate_columns(df)

    logger.info(f"从 MySQL 读取到 {len(df)} 行数据")
    return df


def fetch_sales_data(config: dict, target_date: str) -> pd.DataFrame:
    """
    数据拉取入口。

    参数：
        config: 配置字典（从 config.json 加载）
        target_date: 要拉取的日期，格式 YYYY-MM-DD

    返回：
        pandas DataFrame，包含目标日期的销售数据
    """
    source_type = config["数据源"].get("类型", "excel").lower()

    logger.info(f"数据源类型：{source_type}，目标日期：{target_date}")

    if source_type == "mysql":
        return fetch_from_mysql(config, target_date)
    else:
        return fetch_from_excel(config, target_date)
