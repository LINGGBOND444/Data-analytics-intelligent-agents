"""
报告生成模块
============
将分析结果整理为 Markdown 格式报告，保存到 reports/ 目录。

报告包含：
1. 总体概况
2. 异常商品明细表
3. AI 归因分析
4. 重点建议
"""

import os
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


def generate_report(
    config: dict,
    sales_data: pd.DataFrame,
    anomalies: pd.DataFrame,
    analysis_results: list,
    target_date: str,
    comparison_date: str = None,
) -> str:
    """
    生成 Markdown 分析报告。

    参数：
        config: 配置字典
        sales_data: 当日全部销售数据
        anomalies: 异常产品 DataFrame
        analysis_results: AI 分析结果列表 [{"产品名称": ..., "分析": ...}]
        target_date: 报告日期 YYYY-MM-DD

    返回：
        报告文件路径
    """
    # 报告目录
    report_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
    os.makedirs(report_dir, exist_ok=True)

    report_file = os.path.join(report_dir, f"销售分析报告_{target_date}.md")

    # 统计数据
    total_sales_amount = sales_data["销售额"].sum() if "销售额" in sales_data.columns else 0
    total_sales_volume = sales_data["销售量"].sum() if "销售量" in sales_data.columns else 0
    product_count = len(sales_data)
    anomaly_count = len(anomalies) if not anomalies.empty else 0

    # 异常类型统计
    up_count = 0
    down_count = 0
    zero_count = 0
    if not anomalies.empty and "异常类型" in anomalies.columns:
        types = anomalies["异常类型"].str.cat(sep=" | ") if len(anomalies) > 0 else ""
        up_count = types.count("上涨")
        down_count = types.count("下跌")
        zero_count = types.count("断崖")

    # 构建报告
    lines = []
    lines.append(f"# 📊 销售数据分析报告")
    lines.append(f"")
    lines.append(f"**报告日期**：{target_date}")
    if comparison_date:
        lines.append(f"  |  **环比基准**：{comparison_date}")
    lines.append(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 一、总体概况
    lines.append(f"## 一、总体概况")
    lines.append(f"")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 总销售额 | ¥{total_sales_amount:,.2f} |")
    lines.append(f"| 总销量 | {total_sales_volume:,.0f} 件 |")
    lines.append(f"| 产品数量 | {product_count} 个 |")
    lines.append(f"| 异常产品数 | **{anomaly_count} 个** |")
    if anomaly_count > 0:
        lines.append(f"| 异常上涨 | {up_count} 个 |")
        lines.append(f"| 异常下跌 | {down_count} 个 |")
        if zero_count > 0:
            lines.append(f"| 断崖式下跌 | {zero_count} 个 |")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 二、异常商品明细
    if anomaly_count > 0:
        lines.append(f"## 二、异常商品明细")
        lines.append(f"")
        lines.append(f"| 产品名称 | 昨日销量 | 上期销量 | 销量变化% | 昨日销售额 | 上期销售额 | 销售额变化% | 日进货量 | 异常类型 |")
        lines.append(f"|----------|---------|---------|----------|-----------|-----------|-----------|---------|---------|")

        for _, row in anomalies.iterrows():
            name = row.get("产品名称", "-")
            vol = row.get("销售量", "-")
            prev_vol = row.get("上期销量", "-")
            vol_chg = row.get("销量变化%", "-")
            amt = row.get("销售额", "-")
            prev_amt = row.get("上期销售额", "-")
            amt_chg = row.get("销售额变化%", "-")
            restock = row.get("日进货量", "-")
            anomaly_type = row.get("异常类型", "-")

            # 格式化数值
            vol_str = f"{vol:,.0f}" if isinstance(vol, (int, float)) and not pd.isna(vol) else str(vol)
            prev_vol_str = f"{prev_vol:,.0f}" if isinstance(prev_vol, (int, float)) and not pd.isna(prev_vol) else str(prev_vol)
            amt_str = f"¥{amt:,.2f}" if isinstance(amt, (int, float)) and not pd.isna(amt) else str(amt)
            prev_amt_str = f"¥{prev_amt:,.2f}" if isinstance(prev_amt, (int, float)) and not pd.isna(prev_amt) else str(prev_amt)
            vol_chg_str = f"{vol_chg:+.1f}%" if isinstance(vol_chg, (int, float)) and not pd.isna(vol_chg) else str(vol_chg)
            amt_chg_str = f"{amt_chg:+.1f}%" if isinstance(amt_chg, (int, float)) and not pd.isna(amt_chg) else str(amt_chg)
            restock_str = f"{restock:,.0f}" if isinstance(restock, (int, float)) and not pd.isna(restock) else str(restock)

            # 用 emoji 标记涨跌
            if isinstance(vol_chg, (int, float)) and not pd.isna(vol_chg):
                arrow = "🔴" if vol_chg < -30 else "🟢" if vol_chg > 30 else "➡️"
                vol_chg_str = f"{arrow} {vol_chg_str}"

            lines.append(
                f"| {name} | {vol_str} | {prev_vol_str} | {vol_chg_str} | "
                f"{amt_str} | {prev_amt_str} | {amt_chg_str} | {restock_str} | {anomaly_type} |"
            )

        lines.append(f"")
    else:
        lines.append(f"## 二、异常商品明细")
        lines.append(f"")
        lines.append(f"> ✅ 本日未发现异常产品，所有产品销售情况正常。")
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"")

    # 三、AI 归因分析
    lines.append(f"## 三、AI 归因分析")
    lines.append(f"")

    if analysis_results:
        for i, result in enumerate(analysis_results, 1):
            product_name = result.get("产品名称", f"产品{i}")
            analysis = result.get("分析", "暂无分析")
            lines.append(f"### {i}. {product_name}")
            lines.append(f"")
            lines.append(analysis)
            lines.append(f"")

            # 建议措施
            suggestion = result.get("建议", "")
            if suggestion:
                lines.append(f"**💡 建议措施**：{suggestion}")
                lines.append(f"")
    elif anomaly_count > 0:
        lines.append(f"> ⚠️ AI 分析未启用或未返回结果，请检查配置。")
        lines.append(f"")
    else:
        lines.append(f"> ✅ 无异常产品，无需 AI 分析。")
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"")

    # 四、重点关注
    if anomaly_count > 0:
        lines.append(f"## 四、重点关注")
        lines.append(f"")
        lines.append(f"以下事项建议立即跟进：")
        lines.append(f"")

        num = 1
        for _, row in anomalies.iterrows():
            name = row.get("产品名称", "-")
            anomaly_type = row.get("异常类型", "")
            vol_chg = row.get("销量变化%", None)

            if isinstance(vol_chg, (int, float)) and not pd.isna(vol_chg) and vol_chg <= -threshold(config):
                lines.append(f"{num}. **【紧急】{name}** — 销量下跌 {vol_chg:.1f}%，需立即排查原因")
                num += 1

        if num == 1:
            lines.append(f"{num}. 所有异常产品均无需紧急处理，建议持续观察。")
    else:
        lines.append(f"## 四、重点关注")
        lines.append(f"")
        lines.append(f"> 本日一切正常，无需特别关注。")

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*本报告由销售数据分析智能体自动生成*")

    # 写入文件
    report_content = "\n".join(lines)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info(f"报告已保存至：{report_file}")
    return report_file


def threshold(config: dict) -> float:
    """获取异常阈值"""
    return config.get("异常检测", {}).get("环比阈值_百分比", 30)
