#!/usr/bin/env bash
# 清理 GHCR 旧镜像版本：每个包只保留最近 KEEP 个版本，更旧的删除。
# 用法: bash cleanup-ghcr.sh [KEEP]   (默认 3)
set -euo pipefail

KEEP="${1:-3}"
BASE="/repos/${GITHUB_REPOSITORY}/packages/container"

for pkg in "lobsterai2api-docker%2Fserver" "lobsterai2api-docker%2Fcheckin"; do
  echo "=========== 包: $pkg ==========="
  # 按创建时间倒序取所有版本 id
  ids=$(gh api "${BASE}/${pkg}/versions?per_page=100" \
    --jq 'sort_by(.created_at) | reverse | .[].id' 2>/dev/null) || {
    echo "查询失败（可能无该包或无权限），跳过。"
    continue
  }
  count=$(printf '%s\n' "$ids" | grep -c . || true)
  echo "发现 $count 个版本，保留最近 $KEEP 个"
  i=0
  for vid in $ids; do
    i=$((i + 1))
    if [ "$i" -le "$KEEP" ]; then
      echo "保留 #$i: $vid"
    else
      echo "删除版本 $vid"
      gh api -X DELETE "${BASE}/${pkg}/versions/${vid}" || echo "删除 $vid 失败(跳过)"
    fi
  done
done
echo "清理完成。"