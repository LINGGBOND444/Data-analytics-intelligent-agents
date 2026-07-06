"""
推送通知模块
============
将分析报告推送到钉钉（主）或邮箱（备）。

钉钉推送：
  - 通过群机器人 Webhook 发送 Markdown 消息
  - 篇幅有限，只发送报告摘要 + 关键异常

邮箱推送：
  - 通过 SMTP 发送完整报告
  - 报告内容作为邮件正文
"""

import os
import logging
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

logger = logging.getLogger(__name__)


def send_notification(config: dict, report_path: str, anomaly_count: int, target_date: str):
    """
    推送通知入口。根据配置自动选择渠道。

    参数：
        config: 配置字典
        report_path: 报告文件路径
        anomaly_count: 异常产品数量
        target_date: 报告日期
    """
    # 读取报告内容
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()

    # 生成摘要（截取报告前 500 字，适合推送）
    summary = _generate_summary(report_content, anomaly_count, target_date)

    # 1. 钉钉推送（主）
    ding_config = config.get("推送", {}).get("钉钉", {})
    if ding_config.get("启用", False):
        webhook_url = ding_config.get("Webhook地址", "")
        if webhook_url:
            logger.info("正在推送到钉钉...")
            success = _send_dingtalk(webhook_url, summary, anomaly_count, target_date)
            if success:
                logger.info("✓ 钉钉推送成功")
            else:
                logger.warning("✗ 钉钉推送失败")
        else:
            logger.warning("钉钉已启用但 Webhook 地址为空，跳过")

    # 2. 邮箱推送（备）
    email_config = config.get("推送", {}).get("邮箱", {})
    if email_config.get("启用", False):
        logger.info("正在发送邮件...")
        success = _send_email(email_config, report_content, target_date, report_path)
        if success:
            logger.info("✓ 邮件发送成功")
        else:
            logger.warning("✗ 邮件发送失败")


def _generate_summary(report_content: str, anomaly_count: int, target_date: str) -> str:
    """生成推送摘要。取报告标题 + 概况 + 异常列表，去除过长内容。"""
    lines = report_content.split("\n")

    # 提取关键部分
    summary_parts = []
    in_table = False
    table_lines = []

    for line in lines:
        # 保留标题和总览
        if line.startswith("# ") or line.startswith("## "):
            summary_parts.append(line)
            continue

        # 收集表格行
        if line.startswith("|"):
            in_table = True
            table_lines.append(line)
            continue
        elif in_table and not line.startswith("|"):
            # 表格结束
            in_table = False
            if table_lines and len(table_lines) <= 8:  # 最多保留 8 行表格
                summary_parts.extend(table_lines)
            table_lines = []
            continue

    if table_lines and len(table_lines) <= 8:
        summary_parts.extend(table_lines)

    # 添加尾部提示
    summary_parts.append("")
    summary_parts.append(f"> 共发现 **{anomaly_count}** 个异常产品")
    summary_parts.append(f"> 完整报告请查看本地文件")

    return "\n".join(summary_parts)


def _send_dingtalk(webhook_url: str, summary: str, anomaly_count: int, target_date: str) -> bool:
    """
    发送钉钉机器人消息。

    钉钉 Markdown 消息格式：
    {
        "msgtype": "markdown",
        "markdown": {
            "title": "标题",
            "text": "Markdown 内容"
        }
    }
    """
    try:
        title = f" 销售异常监控 {target_date}"
        if anomaly_count > 0:
            title += f" — ⚠️ {anomaly_count} 个异常"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": summary,
            },
        }

        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        if result.get("errcode") == 0:
            return True
        else:
            logger.error(f"钉钉返回错误：{result.get('errmsg', '未知错误')}")
            return False

    except requests.exceptions.Timeout:
        logger.error("钉钉推送超时")
        return False
    except Exception as e:
        logger.error(f"钉钉推送异常：{e}")
        return False


def _send_email(
    email_config: dict, report_content: str, target_date: str, report_path: str
) -> bool:
    """
    通过 SMTP 发送邮件。

    参数：
        email_config: 邮箱配置
        report_content: 报告内容（作为邮件正文）
        target_date: 报告日期
        report_path: 报告文件路径（作为附件路径）
    """
    try:
        smtp_server = email_config.get("SMTP服务器", "smtp.qq.com")
        smtp_port = email_config.get("SMTP端口", 587)
        sender = email_config.get("发件邮箱", "")
        password = email_config.get("授权码", "")
        receiver = email_config.get("收件邮箱", "")

        if not sender or not password or not receiver:
            logger.warning("邮箱配置不完整，跳过邮件发送")
            return False

        # 构建邮件
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = Header(f"📊 销售分析报告 - {target_date}", "utf-8")

        # 邮件正文（HTML 格式，简单渲染 Markdown 样式）
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: auto;">
        <pre style="white-space: pre-wrap; font-family: inherit;">
{report_content}
        </pre>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # 发送
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.starttls()  # 启用 TLS 加密
        server.login(sender, password)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()

        logger.info(f"邮件已发送至 {receiver}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("邮箱登录失败，请检查邮箱地址和授权码是否正确")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP 发送失败：{e}")
        return False
    except Exception as e:
        logger.error(f"邮件发送异常：{e}")
        return False
