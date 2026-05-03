#!/bin/bash
# ==============================================================
#  打包脚本 - 将项目打包为独立可执行文件
#  需要先安装 PyInstaller: pip install pyinstaller
# ==============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "======================================"
echo "  打包在线考试系统为可执行文件"
echo "======================================"
echo ""

# 检查 PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "正在安装 PyInstaller..."
    pip install pyinstaller --break-system-packages
fi

echo "清理旧构建..."
rm -rf build dist __pycache__

echo "开始打包..."
pyinstaller \
  --onefile \
  --name ExamSystem \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --hidden-import flask \
  --hidden-import werkzeug \
  --hidden-import jinja2 \
  --hidden-import click \
  --hidden-import itsdangerous \
  --hidden-import markupsafe \
  --hidden-import sqlite3 \
  --hidden-import _sqlite3 \
  app.py

echo ""
echo "======================================"
echo "  打包完成！"
echo "  可执行文件位置: dist/ExamSystem"
echo "======================================"
echo ""
echo "运行方式: ./dist/ExamSystem"
echo "首次运行会在同目录下创建 exam_system.db"
