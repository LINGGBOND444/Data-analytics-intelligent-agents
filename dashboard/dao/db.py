"""
[数据访问层] 数据库连接与原子操作模块
================================
职责边界：
- 仅封装数据库连接、查询、写入、删除等原子操作
- 所有 SQL 使用参数化查询，禁止字符串拼接
- 异常统一捕获并包装为标准化错误信息，不暴露原始堆栈
- 严格禁止：包含任何业务逻辑、业务场景SQL拼接、直接被视图层调用
"""

import pymysql
import logging
from typing import Any
from utils.config import load_db_config

logger = logging.getLogger(__name__)


class Database:
    """
    单例数据库连接管理类。

    使用方式：
        db = Database()
        rows = db.execute_query("SELECT * FROM {{table}} WHERE id = %(id)s", {"id": 1})
    """

    _instance = None
    _config: dict = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config = load_db_config()
        return cls._instance

    # ---------- 公开方法（供业务服务层调用） ----------

    def get_connection(self) -> pymysql.Connection:
        """
        获取一个数据库连接。

        返回：
            pymysql.Connection — 数据库连接对象

        异常：
            ConnectionError — 连接失败时抛出，包含友好错误信息
        """
        try:
            conn = pymysql.connect(
                host=self._config["host"],
                port=self._config["port"],
                user=self._config["user"],
                password=self._config["password"],
                database=self._config["database"],
                charset="utf8mb4",
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor,
            )
            return conn
        except pymysql.err.OperationalError as e:
            error_code = e.args[0] if e.args else "未知"
            if error_code == 1045:
                msg = "数据库登录失败，请检查 .env 中的 DB_USER 和 DB_PASSWORD 是否正确"
            elif error_code == 1049:
                msg = f"数据库 '{self._config['database']}' 不存在，请检查 DB_NAME 配置"
            elif error_code in (2003, 2005):
                msg = (
                    f"无法连接到数据库 {self._config['host']}:{self._config['port']}，"
                    "请确认 MySQL 服务已启动且地址正确"
                )
            else:
                msg = f"数据库连接失败：{e}"
            logger.error(msg)
            raise ConnectionError(msg) from e
        except Exception as e:
            msg = f"数据库连接异常：{e}"
            logger.error(msg)
            raise ConnectionError(msg) from e

    def test_connection(self) -> bool:
        """测试数据库连接是否可用。返回 True/False。"""
        try:
            conn = self.get_connection()
            conn.close()
            return True
        except ConnectionError:
            return False

    def execute_query(self, sql: str, params: dict = None) -> list[dict]:
        """
        执行查询 SQL，返回结构化结果列表。

        参数：
            sql: 参数化 SQL 语句（使用 %(key)s 占位符）
            params: 参数字典

        返回：
            list[dict] — 查询结果，每行为一个字典

        使用示例：
            db.execute_query(
                "SELECT * FROM {{table}} WHERE date = %(date)s",
                {"date": "2026-07-10"}
            )
        """
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params or {})
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"查询执行失败：{e}")
            raise RuntimeError(f"数据查询失败：{e}") from e
        finally:
            if conn:
                conn.close()

    def execute_write(self, sql: str, params: dict = None) -> int:
        """
        执行写入 SQL（INSERT / UPDATE / DELETE），返回受影响行数。

        参数：
            sql: 参数化 SQL 语句
            params: 参数字典

        返回：
            int — 受影响的行数
        """
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params or {})
                conn.commit()
                return affected
        except Exception as e:
            logger.error(f"写入操作失败：{e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise RuntimeError(f"数据写入失败：{e}") from e
        finally:
            if conn:
                conn.close()


# ---------- 便捷函数 ----------

# 模块级单例，供上层直接导入使用
_db_instance: Database | None = None


def get_db() -> Database:
    """获取 Database 单例实例。"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
