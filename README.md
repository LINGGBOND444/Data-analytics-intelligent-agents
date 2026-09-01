# 销售数据分析智能体

## 项目概述

这是一个**销售数据分析智能体系统**，实现完整的业务闭环：

```
定时触发 → 数据拉取 → 异常检测 → AI归因分析 → 报告生成 → 主动推送
```

每天早 8:00 自动运行，从 Excel（或 MySQL）读取前一日销售数据，通过环比分析检测异常产品，调用 DeepSeek API 进行 AI 归因分析，生成 Markdown 分析报告，通过钉钉推送给用户。

## 技术架构

- **语言**：Python 3
- **数据分析**：pandas + openpyxl（Excel）、pymysql（MySQL）
- **AI 分析**：DeepSeek API（兼容 Anthropic Messages 协议）
- **定时任务**：Windows 任务计划程序
- **推送**：钉钉 Webhook（主）+ 邮件 SMTP（备）

## 项目结构

```
├── CLAUDE.md                    # 项目说明（本文件）
├── 文件清单.md                   # 完整文件清单，供学习参考
├── .gitignore                   # Git 忽略规则
│
├── backend/                     # ===== 后端：智能体核心系统 =====
│   ├── main.py                  # CLI 主入口，编排整个分析流程
│   ├── config.json              # 配置文件（数据源、阈值、API密钥、推送地址）
│   ├── config.example.json      # 配置模板（不含真实密钥）
│   ├── requirements.txt         # Python 依赖
│   ├── setup.bat                # 一键安装依赖
│   ├── setup_task.bat           # 一键配置 Windows 定时任务
│   ├── generate_test_data.py    # 测试数据生成工具
│   ├── src/                     # 核心分析模块
│   │   ├── data_fetcher.py      # 数据拉取（Excel + MySQL）
│   │   ├── anomaly_detector.py  # 异常检测（环比/同比/规则/库存不足）
│   │   ├── analyzer.py          # AI 归因分析（DeepSeek API）
│   │   ├── reporter.py          # Markdown 报告生成
│   │   └── notifier.py          # 推送通知（钉钉 + 邮箱）
│   ├── scripts/                 # 辅助工具
│   │   ├── init_db.sql          # MySQL 建表脚本 + 测试数据
│   │   └── export_mysql_to_excel.py  # MySQL → Excel 导出脚本
│   ├── data/                    # 存放 Excel 数据文件
│   ├── reports/                 # 生成的 Markdown 分析报告
│   └── logs/                    # 运行日志
│
└── dashboard/                   # ===== 前端：Streamlit 可视化管理面板 =====
    ├── app.py                   # 主入口 + 首页（数据概览看板）
    ├── .env.example             # 环境变量模板（数据库连接配置）
    ├── requirements_dashboard.txt  # 面板新增依赖
    ├── pages/                   # 页面
    │   ├── 2_🤖_任务控制.py      # 智能体任务参数配置 + 启动控制
    │   ├── 3_📋_数据管理.py      # 数据筛选查询 + 新增/删除 + CSV 导出
    │   └── 4_📋_运行日志.py      # 执行历史日志查看
    ├── services/                # 业务服务层
    │   ├── agent_service.py     # 智能体调用封装 + 后台线程管理
    │   └── data_service.py      # 业务数据服务（统计/查询/增删改查）
    ├── dao/                     # 数据访问层
    │   └── db.py                # 单例数据库连接 + 参数化 SQL 操作
    └── utils/                   # 通用工具层
        ├── config.py            # .env 配置读取
        ├── ui_components.py     # 通用 UI 组件（指标卡片、确认弹窗、状态徽章）
        └── common.py            # 通用工具（日期格式化、CSV 导出、安全取值）
```

## 使用方法

1. 双击 `backend/setup.bat` 安装依赖
2. 编辑 `backend/config.json`，配置数据源和推送地址
3. 将销售数据 Excel 放入 `backend/data/` 目录
4. 在 `backend/` 目录下运行 `python main.py` 测试
5. 双击 `backend/setup_task.bat` 创建每日定时任务（需管理员权限）

### Excel 数据格式

| 列名 | 说明 | 必填 |
|------|------|------|
| 日期 | YYYY-MM-DD 格式 | ✓ |
| 产品名称 | 产品名称 | ✓ |
| 销售量 | 销售数量 | ✓ |
| 销售额 | 销售金额 | ✓ |
| 单价 | 产品单价 | - |
| 库存 | 当前库存 | - |

也支持英文列名：date, product, volume/quantity, amount/revenue, price, stock

### MySQL 数据源使用

如果要使用 MySQL 数据库而不是 Excel 文件：

**① 初始化数据库**：在 MySQL 中执行 `backend/scripts/init_db.sql`，会自动创建 `sales` 数据库和 `daily_sales` 表。这个脚本还包含了一些测试数据，方便首次验证。

**② 配置连接**：在 `backend/config.json` 中修改：

```json
"数据源": {
    "类型": "mysql",           // ← 把 "excel" 改为 "mysql"
    "MySQL": {
        "主机": "localhost",    // ← 你的 MySQL 地址
        "端口": 3306,
        "用户名": "root",      // ← 你的 MySQL 用户名
        "密码": "你的密码",     // ← 你的 MySQL 密码
        "数据库名": "sales",
        "表名": "daily_sales",
        "自动导出": true        // ← true = main.py 自动从 MySQL 导出
    }
}
```

**③ 手动导出（可选）**：也可以单独运行导出脚本：

```
python backend/scripts/export_mysql_to_excel.py              # 导出昨天数据
python backend/scripts/export_mysql_to_excel.py 2026-07-06   # 导出指定日期
```

**④ 运行分析**：在 `backend/` 目录下运行 `python main.py`

> **工作原理**：MySQL 模式不会直接拿数据库数据分析，而是先从 MySQL 导出 Excel 放到 `backend/data/` 目录，然后走和 Excel 模式完全一样的分析流程。这样改动最少，也方便排查问题。

## 用户偏好

- **数据源**：Excel 优先，MySQL 已支持（通过导出脚本衔接）
- **推送**：钉钉为主，邮箱备选
- **分析范围**：不做联网搜索，专注数据驱动的异常分析
- **异常阈值**：环比变化 ≥ ±30% 触发异常
- **用户是技术小白**，所有技术操作需详细解释

## AI 助手注意事项

1. 修改代码时，注意用户是技术小白，变更要简单明了
2. 技术操作前先解释"是什么 / 为什么 / 会怎样"
3. 所有可配置参数在 `config.json` 中，不要硬编码
4. 本项目使用 DeepSeek API（兼容 Anthropic 协议），不要改用其他 AI 服务
5. 日志统一用 `logging` 模块，方便排查问题
