@echo off
chcp 65001 >nul
echo ========================================
echo   配置 Windows 定时任务
echo   每天早 8:00 自动运行销售分析
echo ========================================
echo.

:: 获取当前目录的绝对路径
set "SCRIPT_DIR=%~dp0"
set "PYTHON_SCRIPT=%SCRIPT_DIR%main.py"

:: 查找 Python 路径
for /f "tokens=*" %%i in ('where python') do set "PYTHON_PATH=%%i"
if "%PYTHON_PATH%"=="" (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

echo Python 路径：%PYTHON_PATH%
echo 脚本路径：%PYTHON_SCRIPT%
echo.

:: 先删除旧的同名任务（如果存在）
schtasks /delete /tn "销售数据分析智能体" /f >nul 2>&1

:: 创建新的定时任务
:: /sc DAILY       每天运行
:: /st 08:00       早 8:00
:: /tn             任务名称
:: /tr             要执行的命令
schtasks /create ^
    /sc DAILY ^
    /st 08:00 ^
    /tn "销售数据分析智能体" ^
    /tr "\"%PYTHON_PATH%\" \"%PYTHON_SCRIPT%\"" ^
    /rl HIGHEST

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   定时任务创建成功！
    echo   任务名称：销售数据分析智能体
    echo   运行时间：每天早上 8:00
    echo ========================================
    echo.
    echo 提示：
    echo   - 查看任务：在开始菜单搜索"任务计划程序"
    echo   - 手动运行：schtasks /run /tn "销售数据分析智能体"
    echo   - 删除任务：schtasks /delete /tn "销售数据分析智能体" /f
    echo.
) else (
    echo.
    echo [失败] 任务创建失败，请尝试以管理员身份运行此脚本。
    echo 方法：右键 setup_task.bat → 以管理员身份运行
    echo.
)

pause
