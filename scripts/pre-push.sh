#!/bin/sh
# 배포 전 자동 검증 — 코드(.py) 변경이 포함된 푸시에서만 실행.
# 데이터(CSV)만 바뀐 일상 업데이트는 건너뛰어 빠르게 통과.
# 건너뛰려면: git push --no-verify

changed=$(git diff --name-only origin/main HEAD 2>/dev/null)

# origin/main을 못 찾으면(-z) 안전하게 검증 실행, .py 변경 있으면 검증 실행
if [ -z "$changed" ] || echo "$changed" | grep -q '\.py$'; then
  echo "🔍 배포 전 검증..."

  if ! python3 -m py_compile *.py 2>/tmp/gpf_pyc.txt; then
    echo "❌ 구문 오류 — 푸시 중단"
    cat /tmp/gpf_pyc.txt
    exit 1
  fi

  # 계산 로직 검사가 먼저 — 네트워크를 안 쓰고 1초면 끝나서, 틀렸다면
  # 20초짜리 렌더 검사를 기다릴 이유가 없다.
  if ! python3 verify_logic.py > /tmp/gpf_logic.txt 2>&1; then
    grep -v "ScriptRunContext\|MemoryCacheStorage\|NotOpenSSL\|warnings.warn" /tmp/gpf_logic.txt
    echo ""
    echo "❌ 계산 로직 검사 실패 — 푸시를 중단했습니다. (강제로 올리려면: git push --no-verify)"
    exit 1
  fi

  if ! python3 verify_app.py > /tmp/gpf_verify.txt 2>&1; then
    cat /tmp/gpf_verify.txt
    echo ""
    echo "❌ 검증 실패 — 푸시를 중단했습니다. (강제로 올리려면: git push --no-verify)"
    exit 1
  fi
  echo "✅ 배포 전 검증 통과 (계산 로직 + 렌더)"
fi

exit 0
