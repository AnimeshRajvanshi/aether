#!/bin/bash
echo "=== Docker Cleanup Report $(date) ==="
# Prune lines are commented out. Do NOT run them while Claude Code terminals are active.
# docker system prune -f --volumes
# docker volume prune -f
df -h /
echo "Report finished."
