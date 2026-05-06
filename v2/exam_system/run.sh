#!/bin/bash
# ==============================================================
#  在线考试系统 - 构建 & 运行脚本
# ==============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "======================================"
echo "  在线考试系统 ExamSys"
echo "======================================"
echo ""

# ── 依赖检查 ──────────────────────────────
check_dep() {
  python3 -c "import $1" 2>/dev/null && echo "  ✓ $1" || { echo "  ✗ $1 未安装"; return 1; }
}

echo "[ 1/3 ] 检查依赖..."
check_dep flask || pip install flask --break-system-packages -q
check_dep werkzeug || pip install werkzeug --break-system-packages -q
echo ""

# ── 初始化数据库 ──────────────────────────
echo "[ 2/3 ] 初始化数据库..."
python3 - <<'EOF'
import sys
sys.path.insert(0, '.')
from app import init_db
init_db()
print("  ✓ 数据库就绪")
EOF
echo ""

# ── 启动服务 ──────────────────────────────
echo "[ 3/3 ] 启动服务..."
echo ""
echo "  访问地址: http://127.0.0.1:5000"
echo "  管理员:   admin / admin123"
echo "  学生:     student / student123"
echo ""
echo "  按 Ctrl+C 停止服务"
echo ""
python3 app.py
