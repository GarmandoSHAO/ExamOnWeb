@echo off
chcp 65001 > nul
echo.
echo ======================================
echo   在线考试系统 ExamSys
echo ======================================
echo.

cd /d "%~dp0"

echo [1/3] 检查 Python 环境...
python --version 2>nul || (echo 错误: 未找到 Python，请先安装 Python 3.8+ & pause & exit)

echo [2/3] 安装依赖...
pip install flask -q 2>nul
if errorlevel 1 (
    echo 提示: 依赖安装失败，请手动运行: pip install flask
)

echo [3/3] 启动系统...
echo.
echo   访问地址: http://127.0.0.1:5000
echo   管理员:   admin / admin123
echo   学生:     student / student123
echo.
echo   按 Ctrl+C 或关闭窗口可停止服务
echo.
python app.py

pause
