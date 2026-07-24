#!/bin/sh
# Mount a Windows drive letter into /mnt/<drive> and verify Q-SEED path.
# Args: $1=drive (e.g. d), $2=letter (e.g. D), $3=absolute mnt path (/mnt/d/...)
set -e
drive="$1"
letter="$2"
mnt_path="$3"
mkdir -p "/mnt/$drive"

if mountpoint -q "/mnt/$drive"; then
  src=$(findmnt -n -o SOURCE "/mnt/$drive" 2>/dev/null || true)
  fstype=$(findmnt -n -o FSTYPE "/mnt/$drive" 2>/dev/null || true)
  if [ "$fstype" != "drvfs" ]; then
    echo "ERROR: /mnt/$drive is mounted as fstype='$fstype' source='$src' (expected ${letter}: drvfs)" >&2
    exit 1
  fi
  src_norm=$(printf '%s' "$src" | tr 'abcdefghijklmnopqrstuvwxyz\\' 'ABCDEFGHIJKLMNOPQRSTUVWXYZ/')
  letter_u=$(printf '%s' "$letter" | tr 'abcdefghijklmnopqrstuvwxyz' 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
  case "$src_norm" in
    "${letter_u}:"|"${letter_u}:/"|"${letter_u}:/"*)
      ;;
    *)
      echo "ERROR: /mnt/$drive is already mounted from '$src', not ${letter}:" >&2
      exit 1
      ;;
  esac
else
  mount -t drvfs "$letter:" "/mnt/$drive"
fi

if [ ! -d "$mnt_path" ]; then
  echo "Missing data dir: $mnt_path" >&2
  exit 1
fi
ls "$mnt_path" | head -3
