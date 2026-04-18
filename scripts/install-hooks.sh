#!/usr/bin/env bash
# 저장소용 git hook 설치. 로컬 .git/hooks/ 에 복사 + 실행 권한 부여.
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SRC="$REPO_ROOT/scripts"
HOOKS_DST="$REPO_ROOT/.git/hooks"

for hook in pre-push; do
  install -m 0755 "$HOOKS_SRC/$hook" "$HOOKS_DST/$hook"
  echo "✅ installed: .git/hooks/$hook"
done
