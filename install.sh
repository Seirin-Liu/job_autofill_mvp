#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
[ -f .env ] || cp .env.example .env
echo "安装完成。编辑 .env（可选）后运行 ./start.sh"
