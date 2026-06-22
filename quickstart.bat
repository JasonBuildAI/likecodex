@echo off
title LikeCodex Quick Start

:: 确保在正确的目录下运行
cd /d "%~dp0"

echo ============================================
echo    LikeCodex - AI Coding Assistant
echo ============================================
echo.
echo 当前目录: %CD%
echo.
echo 请选择启动模式:
echo   1) Lite 极简模式 (仅内置 UI, 无需编译 Rust)
echo   2) 完整模式 (Web UI + API, 需要编译 Rust)
echo   3) 安装 Tauri 桌面版
echo   4) 退出
echo.
set /p choice="请输入选项 (1/2/3/4): "

if "%choice%"=="1" (
    echo.
    echo ===== 启动 Lite 极简模式 =====
    echo 仅启动 Python 引擎 + 内置 Lite UI, 无需 Rust 编译
    echo 首次启动需要输入 API Key
    echo ================================
    echo.
    powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\likecodex-start.ps1" -Mode lite
    echo.
    echo PowerShell 已退出，按任意键关闭...
    goto :end
)

if "%choice%"=="2" (
    echo.
    echo ===== 启动完整模式 =====
    echo 将构建 Rust + 启动引擎/API/Web UI
    echo 首次构建需要 5-10 分钟
    echo ==========================
    echo.
    powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\likecodex-start.ps1" -Mode full
    echo.
    echo PowerShell 已退出，按任意键关闭...
    goto :end
)

if "%choice%"=="3" (
    echo.
    echo ===== Tauri 桌面版 =====
    powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\start-desktop.ps1"
    echo.
    echo 桌面版已退出，按任意键关闭...
    goto :end
)

if "%choice%"=="4" (
    echo 退出。
    goto :end
)

echo 无效选项，退出。
:end
echo.
pause
