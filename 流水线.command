#!/bin/zsh
# ============================================
# Spec-Kit 流水线启动器（根目录双击即用）
# 用法：
#   双击            → 跑全部门禁
#   终端执行:
#     ./流水线.command --list
#     ./流水线.command --gate pattern_regression
#     ./流水线.command --dry-run
# ============================================
cd "$(dirname "$0")/spec-kit-pipeline" || { echo "找不到 spec-kit-pipeline 目录"; exit 1; }

if [ $# -eq 0 ]; then
  /opt/homebrew/bin/python3 pipeline.py
else
  /opt/homebrew/bin/python3 pipeline.py "$@"
fi

echo ""
echo "（按回车关闭窗口）"
read -r
