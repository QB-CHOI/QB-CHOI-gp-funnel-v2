#!/bin/zsh
# 데이터 자동 갱신 — launchd 진입점.
#
# 2단계로 나눈 이유:
#   ① node : macOS TCC로 보호된 ~/Documents의 키워드툴 캐시를 읽어
#            inbox/market/ 으로 복사 (node는 이미 전체 디스크 접근 권한 보유)
#   ② python : 보호되지 않은 위치의 파일만 읽어 집계·업로드
#   → 사용자가 시스템 설정을 건드리지 않아도 완전 자동으로 돌아간다.
cd "$(dirname "$0")/.." || exit 1

if command -v node >/dev/null 2>&1; then
  node scripts/stage_keyword_cache.js
else
  echo "[warn] node 없음 — 키워드툴 캐시 스테이징 건너뜀"
fi

exec /usr/bin/python3 scripts/auto_refresh.py "$@"
