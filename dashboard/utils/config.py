"""
[通用工具与组件层] 配置读取模块
======================
从 .env 文件读取环境变量，提供统一的配置入口。

职责边界：
- 仅负责读取和校验环境变量，不包含任何业务逻辑
- 可被任意上层模块调用
"""

import os
from dotenv import load_dotenv

# 自动加载项目根目录下的 .env 文件
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".env",
)
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH)
else:
    # 尝试默认查找路径
    load_dotenv()


def load_db_config() -> dict:
    """
    从 .env 读取 MySQL 数据库配置。

    返回：
        dict: {
            "host": str,    数据库主机地址
            "port": int,    数据库端口
            "user": str,    数据库用户名
            "password": str,数据库密码
            "database": str, 数据库名
        }

    如果 .env 不存在或缺少必要字段，返回默认值并给出缺省警告。
    """
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "sales"),
    }

    # 检查必要字段是否已配置
    missing = []
    if not config["password"]:
        missing.append("DB_PASSWORD")
    if missing:
        print(
            f"⚠️  警告：以下环境变量未配置：{missing}\n"
            f"   请复制 .env.example 为 .env 并填入真实值"
        )
    return config
