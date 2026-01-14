@echo off
REM V7.0交易系统 - Windows启动脚本

echo ===============================================================================
echo V7.0 非线性动力学交易系统
echo ===============================================================================
echo.
echo 正在启动系统...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Python未安装或不在PATH中
    echo 请先安装Python 3.7+
    pause
    exit /b 1
)

REM 检查依赖是否安装
python -c "import numpy, pandas, scipy, requests, schedule" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装依赖包...
    pip install -r requirements.txt
)

REM 启动系统
echo [启动] V7.0交易系统
python v70_trader_runner.py

pause
