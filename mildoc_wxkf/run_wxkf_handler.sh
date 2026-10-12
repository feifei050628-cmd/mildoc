#!/bin/bash
echo "Mildoc wxkf handler Starting... "

uv sync

export LOGURU_LEVEL=INFO

nohup uv run kf_event_handler.py >> mildoc_wxkf_handler.log 2>&1 &

echo $! > mildoc_wxkf_handler.pid
echo "Mildoc wxkf handler started, PID: $(cat mildoc_wxkf_handler.pid)"