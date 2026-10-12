#!/bin/bash
echo "Mildoc wxkf callback Starting... "

uv sync

nohup uv run gunicorn --worker-class gthread --workers 2 --threads 4 --keep-alive 5 \
  --bind 0.0.0.0:8890 wxkf_callback_app:app >> mildoc_wxkf_callback.log 2>&1 &

echo $! > mildoc_wxkf_callback.pid
echo "Mildoc wxkf callback started, PID: $(cat mildoc_wxkf_callback.pid)"