#!/bin/sh
# 배포 전 검증 훅 설치 — 재클론 후 1회 실행: sh scripts/install-hooks.sh
HOOK=".git/hooks/pre-push"
cp scripts/pre-push.sh "$HOOK"
chmod +x "$HOOK"
echo "✅ pre-push 훅 설치 완료"
