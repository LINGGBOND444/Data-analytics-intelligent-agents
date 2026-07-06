"""
异常检测模块
============
对销售数据进行环比/同比分析，标记异常产品。

检测规则：
1. 环比检测：昨日 vs 前日，销量/销售额变化 ≥ ±阈值% → 异常
2. 零销量检测：昨日销量为 0 但前日有正常销量 → 断崖式下跌
3. 同比检测（可选）：昨日 vs 去年同期（需要一年以上历史数据）
"""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def detect_anomalies(config: dict, sales_data: pd.DataFrame) -> pd.DataFrame:
    """
    检测异常产品。

    参数：
        config: 配置字典
        sales_data: 当日销售数据 DataFrame
                   必须包含列：日期、产品名称、销售量、销售额

    返回：
        异常产品 DataFrame，包含额外列：
        - 异常类型：上涨/下跌/断崖式下跌
        - 销量变化%：销售量环比变化百分比
        - 销售额变化%：销售额环比变化百分比
        - 前日销量、前日销售额：供参考
    """
    threshold = config["异常检测"]["环比阈值_百分比"]  # 默认 30%
    enable_zero_check = config["异常检测"].get("零销量检测", True)

    df = sales_data.copy()

    # 确保数值列是数字类型
    df["销售量"] = pd.to_numeric(df["销售量"], errors="coerce")
    df["销售额"] = pd.to_numeric(df["销售额"], errors="coerce")
    df["单价"] = pd.to_numeric(df["单价"], errors="coerce")
    df["库存"] = pd.to_numeric(df["库存"], errors="coerce")

    logger.info(f"异常阈值：±{threshold}%，共 {len(df)} 个产品待检测")

    # ----- 计算前日数据（需要从前一日文件中获取）-----
    # 策略：
    # 1. 如果原始数据已自带前日列 → 直接使用
    # 2. 否则 → 尝试从 data/ 目录读取前一日文件来合并

    if "前日销量" in df.columns and df["前日销量"].notna().any():
        # 原始数据中已包含前日数据（可能是手动合并好的多日数据）
        logger.info("数据中已包含前日销量列，直接使用")
    else:
        # 尝试从历史文件加载前日数据
        df = _try_load_previous_day(config, df)
        # 如果加载后还是没有前日数据，初始化为 NaN
        if "前日销量" not in df.columns:
            df["前日销量"] = np.nan
        if "前日销售额" not in df.columns:
            df["前日销售额"] = np.nan

    # ----- 环比计算 -----
    df["销量变化%"] = np.where(
        df["前日销量"].notna() & (df["前日销量"] > 0),
        ((df["销售量"] - df["前日销量"]) / df["前日销量"] * 100).round(1),
        np.nan
    )

    df["销售额变化%"] = np.where(
        df["前日销售额"].notna() & (df["前日销售额"] > 0),
        ((df["销售额"] - df["前日销售额"]) / df["前日销售额"] * 100).round(1),
        np.nan
    )

    # ----- 标记异常 -----
    anomalies = []

    for _, row in df.iterrows():
        vol_change = row.get("销量变化%", np.nan)
        amt_change = row.get("销售额变化%", np.nan)

        # 跳过没有前日数据的产品
        if pd.isna(vol_change) and pd.isna(amt_change):
            continue

        row_anomalies = []

        # 检测销量异常
        if not pd.isna(vol_change):
            if vol_change >= threshold:
                row_anomalies.append(f"销量异常上涨 +{vol_change}%")
            elif vol_change <= -threshold:
                row_anomalies.append(f"销量异常下跌 {vol_change}%")

        # 检测销售额异常
        if not pd.isna(amt_change):
            if amt_change >= threshold:
                row_anomalies.append(f"销售额异常上涨 +{amt_change}%")
            elif amt_change <= -threshold:
                row_anomalies.append(f"销售额异常下跌 {amt_change}%")

        # 零销量检测
        if enable_zero_check:
            prev_vol = row.get("前日销量", np.nan)
            cur_vol = row.get("销售量", 0)
            if not pd.isna(prev_vol) and prev_vol > 0 and cur_vol == 0:
                row_anomalies.append("断崖式下跌（昨日销量归零）")

        if row_anomalies:
            anomalies.append({
                **row.to_dict(),
                "异常类型": " | ".join(row_anomalies),
            })

    result = pd.DataFrame(anomalies) if anomalies else pd.DataFrame()

    if result.empty:
        logger.info("未发现异常产品 ✓")
    else:
        logger.info(f"发现 {len(result)} 个异常产品：")
        for _, r in result.iterrows():
            logger.info(f"  - {r['产品名称']}：{r['异常类型']}")

    return result


def _try_load_previous_day(config: dict, df: pd.DataFrame) -> pd.DataFrame:
    """
    尝试从 data/ 目录加载前一天的数据文件，用于计算环比。
    如果找不到前一天的文件，则前日数据保持为 NaN。
    """
    import os
    import glob
    from datetime import datetime, timedelta

    try:
        data_dir = config["数据源"].get("Excel文件目录", "./data")
        if data_dir.startswith("./"):
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), data_dir[2:]
            )

        # 推断前一天的日期
        dates = pd.to_datetime(df["日期"]).dropna()
        if len(dates) == 0:
            return df
        target_date = pd.to_datetime(dates.iloc[0])
        prev_date = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_short = (target_date - timedelta(days=1)).strftime("%Y%m%d")

        # 搜索前一天的 Excel 文件
        files = glob.glob(f"{data_dir}/*.xlsx") + glob.glob(f"{data_dir}/*.csv")
        prev_file = None
        for f in files:
            if prev_date in f or prev_short in f:
                prev_file = f
                break

        if prev_file is None:
            logger.info(f"未找到前一日（{prev_date}）的数据文件，跳过环比计算")
            return df

        logger.info(f"找到前一日数据文件：{os.path.basename(prev_file)}")

        # 读取前一日数据
        import pandas as _pd
        if prev_file.endswith(".csv"):
            prev_df = _pd.read_csv(prev_file, encoding="utf-8-sig")
        else:
            prev_df = _pd.read_excel(prev_file, engine="openpyxl")

        # 规范化列名
        from src.data_fetcher import _normalize_columns
        prev_df = _normalize_columns(prev_df)

        # 确保有产品名称列
        if "产品名称" not in prev_df.columns:
            return df

        prev_df["销售量"] = _pd.to_numeric(prev_df["销售量"], errors="coerce")
        prev_df["销售额"] = _pd.to_numeric(prev_df["销售额"], errors="coerce")

        # 合并前日数据
        prev_map = prev_df.set_index("产品名称")[["销售量", "销售额"]]
        prev_map.columns = ["前日销量", "前日销售额"]

        df = df.join(prev_map, on="产品名称")
        logger.info(f"成功合并前日数据，{df['前日销量'].notna().sum()} 个产品可环比")

    except Exception as e:
        logger.warning(f"加载前日数据失败：{e}，跳过环比计算")

    return df
