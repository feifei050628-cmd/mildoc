#!/bin/bash
echo "Mildoc wxkf handler Starting... "

uv sync

export LOGURU_LEVEL=INFO

uv run kf_event_handler.py