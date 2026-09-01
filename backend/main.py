"""
销售数据分析智能体 — 主程序
============================
每天自动运行，完成：数据拉取 → 异常检测 → AI分析 → 报告生成 → 推送通知
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta

# 把项目根目录加入 Python 搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_fetcher import fetch_sales_data
from src.anomaly_detector import detect_anomalies
from src.analyzer import analyze_anomalies
from src.reporter import generate_report
from src.notifier import send_notification


def setup_logging():
    """配置日志：同时输出到文件和终端"""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"run_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    """主流程：按顺序执行整个分析管线"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("销售数据分析智能体 启动")
    logger.info("=" * 60)

    try:
        # 1. 加载配置
        config = load_config()
        logger.info("✓ 配置文件加载成功")

        # 2. 数据拉取
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        logger.info(f"正在拉取 {target_date} 的销售数据...")

        # ---- MySQL 模式：先从数据库导出为 Excel ----
        source_type = config["数据源"].get("类型", "excel").lower()
        mysql_cfg = config["数据源"].get("MySQL", {})
        if source_type == "mysql" and mysql_cfg.get("自动导出", True):
            logger.info("数据源为 MySQL，正在从数据库导出 Excel...")
            from scripts.export_mysql_to_excel import export_to_excel
            export_to_excel(config, target_date)

        sales_data = fetch_sales_data(config, target_date)
        logger.info(f"✓ 数据拉取完成，共 {len(sales_data)} 条记录")

        if sales_data.empty:
            logger.warning("没有数据，程序退出")
            return

        # 3. 异常检测
        logger.info("正在进行异常检测...")
        anomalies, comparison_date = detect_anomalies(config, sales_data)
        if comparison_date:
            logger.info(f"  环比基准日期：{comparison_date}")
        logger.info(f"✓ 异常检测完成，发现 {len(anomalies)} 个异常")

        # 4. AI 归因分析（仅在有异常时触发）
        analysis_results = []
        if config.get("AI分析", {}).get("启用", True) and not anomalies.empty:
            logger.info("正在进行 AI 归因分析...")
            analysis_results = analyze_anomalies(config, anomalies, sales_data, comparison_date)
            logger.info(f"✓ AI 分析完成，共 {len(analysis_results)} 条分析结论")
        elif anomalies.empty:
            logger.info("无异常产品，跳过 AI 分析")

        # 5. 报告生成
        logger.info("正在生成分析报告...")
        report_path = generate_report(config, sales_data, anomalies, analysis_results, target_date, comparison_date)
        logger.info(f"✓ 报告已生成：{report_path}")

        # 6. 推送通知
        logger.info("正在推送通知...")
        send_notification(config, report_path, len(anomalies), target_date)
        logger.info("✓ 推送完成")

        logger.info("=" * 60)
        logger.info("全部流程完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"运行出错：{e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
