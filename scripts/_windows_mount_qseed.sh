#!/bin/sh
# Mount a Windows drive letter into /mnt/<drive> and verify Q-SEED path.
# Args: $1=drive (e.g. d), $2=letter (e.g. D), $3=absolute mnt path (/mnt/d/...)
set -e
drive="$1"
letter="$2"
mnt_path="$3"
mkdir -p "/mnt/$drive"
mountpoint -q "/mnt/$drive" || mount -t drvfs "$letter:" "/mnt/$drive"
if [ ! -d "$mnt_path" ]; then
  echo "Missing data dir: $mnt_path" >&2
  exit 1
fi
ls "$mnt_path" | head -3
