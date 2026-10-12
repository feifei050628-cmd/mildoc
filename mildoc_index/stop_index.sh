#!/bin/bash
echo "Mildoc index Stopping... "

PID_FILE="mildoc_index.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null && echo "Stopped PID $PID" || echo "Process $PID not found"
    rm -f "$PID_FILE"
else
    echo "PID file not found"
fi