# 📝 在线考试系统 - ExamSys

基于 **Flask + SQLite** 构建的轻量级在线考试系统，无需数据库服务器，开箱即用。

---

## 🚀 快速启动

### 方法一：直接运行（推荐开发使用）

```bash
# Linux / macOS
pip install flask
bash run.sh

# Windows
双击 run.bat
```

访问 http://127.0.0.1:5000

### 方法二：打包为独立可执行文件

```bash
pip install pyinstaller
bash build.sh        # Linux/macOS
# 或
pyinstaller exam_system.spec   # 使用 spec 文件
```

打包完成后，`dist/ExamSystem`（或 `dist/ExamSystem.exe`）即可独立运行，无需 Python 环境。

---

## 👤 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 学生 | student | student123 |

---

## ✨ 功能特性

### 学生端
- 📋 考试大厅：浏览并参加已发布的考试
- ⏱ 倒计时答题：超时自动提交
- 📊 实时进度追踪：显示答题完成情况
- 📝 详细成绩报告：每题对错、标准答案、解析

### 管理端
- 📊 数据仪表盘：考试数量、学生数、通过率统计
- 📋 考试管理：创建/编辑/发布/关闭/删除考试
- ❓ 题目管理：支持单选、多选、判断、填空四种题型
- 📈 成绩管理：查看所有学生成绩，支持按考试筛选
- 👥 用户管理：查看用户、重置密码、删除账号

---

## 📁 项目结构

```
exam_system/
├── app.py                  # 主程序（Flask 路由 + 数据库）
├── exam_system.db          # SQLite 数据库（运行后自动生成）
├── templates/              # HTML 模板
│   ├── base.html           # 基础布局
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── student_dashboard.html  # 学生考试大厅
│   ├── exam_take.html      # 答题页面
│   ├── exam_result.html    # 成绩详情
│   ├── admin_dashboard.html    # 管理控制台
│   ├── admin_exams.html    # 考试管理
│   ├── admin_exam_edit.html    # 考试编辑
│   ├── admin_questions.html    # 题目列表
│   ├── admin_question_edit.html # 题目编辑
│   ├── admin_records.html  # 成绩管理
│   └── admin_users.html    # 用户管理
├── static/                 # 静态文件（预留）
├── run.sh                  # Linux/macOS 启动脚本
├── run.bat                 # Windows 启动脚本
├── build.sh                # 打包脚本
├── exam_system.spec        # PyInstaller 配置
└── README.md               # 本文档
```

---

## 🎯 题型说明

| 题型 | 说明 | 答案格式 |
|------|------|----------|
| 单选题 | 从 A/B/C/D 选一个 | A |
| 多选题 | 选多个选项 | A,B,D |
| 判断题 | 选正确/错误 | A（正确）或 B（错误）|
| 填空题 | 直接输入文字 | 不区分大小写 |

---

## 🛠 技术栈

- **后端**: Python 3.8+ / Flask
- **数据库**: SQLite（内置，无需安装）
- **前端**: 原生 HTML/CSS/JS（无框架依赖）
- **打包**: PyInstaller（可选）
