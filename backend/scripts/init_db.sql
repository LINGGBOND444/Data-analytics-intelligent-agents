-- ============================================
-- 销售数据分析智能体 — 数据库初始化脚本
-- ============================================
-- 使用方法：
--   1. 打开 MySQL 命令行或 Navicat 等工具
--   2. 复制本文件全部内容
--   3. 粘贴执行即可
--
-- 执行后会：
--   - 创建 sales 数据库（如果不存在）
--   - 创建 daily_sales 表（如果不存在）
-- ============================================

-- 创建数据库（使用 utf8mb4 编码，支持中文和 emoji）
CREATE DATABASE IF NOT EXISTS sales
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

-- 切换到 sales 数据库
USE sales;

-- 创建每日销售数据表
CREATE TABLE IF NOT EXISTS daily_sales (
    id       INT             AUTO_INCREMENT  PRIMARY KEY     COMMENT '自增主键',
    date     DATE            NOT NULL                        COMMENT '销售日期，格式 YYYY-MM-DD',
    product  VARCHAR(100)    NOT NULL                        COMMENT '产品名称',
    volume   DECIMAL(10, 2)  NOT NULL DEFAULT 0              COMMENT '销售量（件）',
    amount   DECIMAL(12, 2)  NOT NULL DEFAULT 0              COMMENT '销售额（元）',
    price    DECIMAL(10, 2)  NOT NULL DEFAULT 0              COMMENT '单价（元）',
    restock  DECIMAL(10, 2)  NOT NULL DEFAULT 0              COMMENT '日进货量（件），进货时间早于销售时间',
    stock    DECIMAL(10, 2)  NOT NULL DEFAULT 0              COMMENT '当前库存（件）',

    -- 索引：加速按日期和产品名查询
    INDEX idx_date       (date),
    INDEX idx_product    (product),
    -- 联合唯一索引：同一天同一产品不重复
    UNIQUE INDEX idx_date_product (date, product)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日销售数据表';

-- 插入一些测试数据（方便初次验证）
-- 如果不需要可以删除下面这段
INSERT IGNORE INTO daily_sales (date, product, volume, amount, price, restock, stock) VALUES
    ('2026-07-05', '产品A-洗发水',   100, 5000, 50,  80,  200),
    ('2026-07-05', '产品B-沐浴露',   50,  2000, 40,  60,  80),
    ('2026-07-05', '产品C-护手霜',   30,  900,  30,  20,  45),
    ('2026-07-05', '产品D-洗面奶',   80,  6400, 80,  50,  120),
    ('2026-07-05', '产品E-面膜套装', 20,  2000, 100, 30,  60),
    ('2026-07-05', '产品F-防晒霜',   60,  3600, 60,  40,  90),
    ('2026-07-05', '产品G-精华液',   40,  8000, 200, 20,  50),
    ('2026-07-06', '产品A-洗发水',   50,  2500, 50,  0,   150),
    ('2026-07-06', '产品B-沐浴露',   90,  3600, 40,  0,   30),
    ('2026-07-06', '产品C-护手霜',   0,   0,    30,  0,   45),
    ('2026-07-06', '产品D-洗面奶',   88,  7040, 80,  80,  110),
    ('2026-07-06', '产品E-面膜套装', 22,  1100, 50,  0,   55),
    ('2026-07-06', '产品F-防晒霜',   55,  3300, 60,  60,  85),
    ('2026-07-06', '产品G-精华液',   42,  8400, 200, 10,  48);
