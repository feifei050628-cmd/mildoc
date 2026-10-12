#!/bin/bash
echo "Mildoc index Starting... "

uv sync

uv run oss_event_handler.py