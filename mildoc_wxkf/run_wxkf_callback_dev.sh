#!/bin/bash
echo "Mildoc wxkf callback Starting... "


uv run gunicorn --worker-class gthread --workers 2 --threads 4 --keep-alive 5 \
  --bind 0.0.0.0:8890 wxkf_callback_app:app