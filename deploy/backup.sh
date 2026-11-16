#!/usr/bin/env bash
# Fab Bot 数据备份 (Linux cron 用): deploy/backup.sh [备份目录]
set -euo pipefail
DEST="${1:-/var/fabbot-backup}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/data"
[ -d "$SRC" ] || { echo "找不到数据目录 $SRC"; exit 1; }
STAMP=$(date +%Y%m%d_%H%M%S)
TARGET="$DEST/$STAMP"
mkdir -p "$TARGET"
# app.db 用 SQLite 在线备份 (不停服); 其余直接拷贝
if command -v sqlite3 >/dev/null; then
  sqlite3 "$SRC/app.db" ".backup '$TARGET/app.db'"   # 在线一致性快照, 不动源库 WAL
  cp -r "$SRC"/knowledge "$SRC"/notes_export "$TARGET"/ 2>/dev/null || true
  [ -d "$SRC/vector_store" ] && cp -r "$SRC/vector_store" "$TARGET/vector_store"
else
  cp -r "$SRC"/. "$TARGET"/
fi
# config.yaml 也纳入备份集 (管理后台配置页运行时会改写, 与数据同等重要)
if [ -f "$ROOT/config.yaml" ]; then cp "$ROOT/config.yaml" "$TARGET/config.yaml"; fi
echo "备份完成: $TARGET"
# 保留策略: 按时间戳目录名排序, 仅保留最近 14 份, 更旧的整份删除
ls -1 "$DEST" | sort | head -n -14 | while read -r old; do rm -rf "$DEST/$old"; done
