#!/bin/bash
echo "Mildoc Admin Starting... "

uv sync

# 调试运行
uv run gunicorn -c gunicorn.config.py admin_api:app