#!/bin/bash
echo "Mildoc index Starting... "

uv sync

nohup uv run oss_event_handler.py >> mildoc_index.log 2>&1 &

echo $! > mildoc_index.pid
echo "Mildoc index started, PID: $(cat mildoc_index.pid)"