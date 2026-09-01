@echo off
chcp 65001 >nul
echo ========================================
echo   销售数据分析智能体 — 一键安装
echo ========================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/2] 检测到 Python 环境...
python --version
echo.

echo [2/2] 安装依赖包...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if %errorlevel% neq 0 (
    echo.
    echo [警告] 使用清华源安装失败，尝试默认源...
    pip install -r requirements.txt
)

echo.
echo ========================================
echo   安装完成！
echo   接下来请编辑 config.json 配置数据源和推送地址
echo   然后运行：python main.py
echo ========================================
pause
