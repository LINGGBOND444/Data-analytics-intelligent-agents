"""
AI 归因分析模块
===============
调用 DeepSeek API（兼容 Anthropic 协议），对异常产品进行深度归因分析。

分析维度：
- 库存变化 → 是否缺货导致销量下降？
- 价格变化 → 是否调价影响销售？
- 历史趋势 → 是否是季节性波动？
- 数据关联 → 多产品同时下跌是否暗示市场变化？
"""

import json
import logging
import requests
import pandas as pd

logger = logging.getLogger(__name__)

# DeepSeek API 兼容 Anthropic Messages 协议
ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic/v1/messages"


def _build_analysis_prompt(anomalies: pd.DataFrame, sales_data: pd.DataFrame) -> str:
    """构建发送给 AI 的分析提示词"""

    # 异常产品摘要
    anomaly_lines = []
    for _, row in anomalies.iterrows():
        name = row.get("产品名称", "-")
        anomaly_type = row.get("异常类型", "-")
        vol = row.get("销售量", "-")
        prev_vol = row.get("前日销量", "-")
        vol_chg = row.get("销量变化%", "-")
        amt = row.get("销售额", "-")
        prev_amt = row.get("前日销售额", "-")
        amt_chg = row.get("销售额变化%", "-")
        price = row.get("单价", "-")
        stock = row.get("库存", "-")

        anomaly_lines.append(
            f"- **{name}**：{anomaly_type}\n"
            f"  销量：{prev_vol} → {vol} （变化 {vol_chg}%）\n"
            f"  销售额：{prev_amt} → {amt} （变化 {amt_chg}%）\n"
            f"  单价：{price} | 库存：{stock}"
        )

    anomaly_text = "\n".join(anomaly_lines)

    # 全局数据概况
    total_products = len(sales_data)
    total_sales = sales_data["销售额"].sum() if "销售额" in sales_data.columns else 0

    # 库存和价格概况
    stock_info = ""
    price_info = ""
    if "库存" in sales_data.columns:
        low_stock = (sales_data["库存"] < 10).sum()
        stock_info = f"库存不足（<10）的产品：{low_stock} 个"
    if "单价" in sales_data.columns:
        avg_price = sales_data["单价"].mean()
        price_info = f"平均单价：¥{avg_price:.2f}"

    prompt = f"""你是一位资深的销售数据分析师。请对以下异常产品进行深度归因分析。

## 总体数据
- 分析日期：{sales_data['日期'].iloc[0] if '日期' in sales_data.columns else '最近一天'}
- 产品总数：{total_products} 个
- 总销售额：¥{total_sales:,.2f}
- {stock_info}
- {price_info}

## 异常产品详情

{anomaly_text}

## 分析要求

请对每个异常产品从以下维度进行分析：

1. **库存因素**：库存是否不足？是否缺货导致销量下降？
2. **价格因素**：单价是否合理？是否有调价迹象？
3. **趋势判断**：是短期波动还是趋势性变化？是否可能是季节性因素？
4. **关联分析**：多个产品同时异常是否存在关联？是否暗示整体市场变化？
5. **建议措施**：针对每个异常产品给出具体的行动建议。

## 输出格式

请用 Markdown 格式输出，每个产品单独一节。最后给出一个综合分析总结。
注意：分析要具体，避免泛泛而谈。如果数据不足以判断某个维度，请明确说明"数据不足，无法判断"。
请用中文输出。"""

    return prompt


def analyze_anomalies(
    config: dict, anomalies: pd.DataFrame, sales_data: pd.DataFrame
) -> list:
    """
    调用 AI 对异常产品进行归因分析。

    参数：
        config: 配置字典
        anomalies: 异常产品 DataFrame
        sales_data: 全部当日数据

    返回：
        [{"产品名称": "xxx", "分析": "...", "建议": "..."}]
    """
    if anomalies.empty:
        return []

    ai_config = config.get("AI分析", {})
    api_key = ai_config.get("API密钥", "")
    model = ai_config.get("模型", "deepseek-v4-pro")

    if not api_key:
        logger.warning("AI 分析 API 密钥未配置，跳过分析")
        return []

    prompt = _build_analysis_prompt(anomalies, sales_data)

    logger.info(f"正在调用 AI 模型 ({model}) 进行归因分析...")
    logger.info(f"分析 {len(anomalies)} 个异常产品")

    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = requests.post(
            ANTHROPIC_BASE_URL,
            headers=headers,
            json=payload,
            timeout=120,  # AI 分析可能需要较长时间
        )
        response.raise_for_status()

        result = response.json()

        # 解析 Anthropic Messages 格式的响应
        ai_text = ""
        if "content" in result:
            # Anthropic 格式: {"content": [{"type": "text", "text": "..."}]}
            for block in result["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    ai_text += block.get("text", "")
        elif "choices" in result:
            # OpenAI 兼容格式
            ai_text = result["choices"][0]["message"]["content"]

        if not ai_text:
            logger.warning("AI 返回了空内容")
            return []

        logger.info(f"AI 分析完成，返回 {len(ai_text)} 字符")

        # 将 AI 的完整分析按产品拆分
        # 策略：把完整分析作为整体，同时为每个异常产品创建条目
        results = []
        for _, row in anomalies.iterrows():
            product_name = row.get("产品名称", "未知产品")
            results.append({
                "产品名称": product_name,
                "分析": ai_text,  # 包含所有产品的完整分析
                "建议": "",
            })

        return results

    except requests.exceptions.Timeout:
        logger.error("AI 分析请求超时（120秒）")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"AI 分析请求失败：{e}")
        return []
    except Exception as e:
        logger.error(f"AI 分析异常：{e}")
        return []
