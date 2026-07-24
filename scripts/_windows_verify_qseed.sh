#!/bin/sh
# Fail if Compose bind left /data/qseed empty.
set -e
entries=$(ls /data/qseed | wc -l)
ls /data/qseed | head -5
if [ "$entries" -eq 0 ]; then
  echo "ERROR: /data/qseed is empty (bind mount failed)" >&2
  exit 1
fi
echo "entries=$entries"
