"""배포 전 앱 렌더 검증.

실행: python3 verify_app.py

Streamlit Cloud는 push하면 바로 배포되므로, 터지는 코드를 올리면
사이트가 죽는다. 이 스크립트는 실제로 사이트를 죽였던 유형의 오류를
배포 전에 잡는다.

  1. 렌더 예외        — 모든 탭을 실제로 그려보고 예외 확인
                        (예: plotly add_vline TypeError로 추이 탭 전체가 죽었던 건)
  2. 제거 예정 API    — Streamlit 버전이 오르면 죽는다
                        (예: use_container_width, 제거 예정일 2025-12-31)
  3. 라이브러리 경고  — pandas 등의 FutureWarning. 당장 죽지는 않지만 조용히
                        동작이 바뀔 수 있어 알려만 준다(실패로 치지 않음)

문구를 좁게 잡으면 안 된다 — 2번을 "will be removed after"로만 찾다가,
문구가 "will be removed in a future release"인 plotly_chart 경고 29건을
통째로 놓쳤다(v4.80에서 발견). 건수만 세지 말고 무엇인지 함께 출력한다.
"""
import contextlib
import io
import re
import sys

APP = "app.py"


def _uniq(patterns, log) -> list[str]:
    """로그에서 패턴에 걸린 문장을 중복 없이 (건수와 함께) 모은다."""
    found = {}
    for pat in patterns:
        for m in re.findall(pat, log):
            line = " ".join(str(m).split())[:160]
            found[line] = found.get(line, 0) + 1
    return [f"{v}회 — {k}" for k, v in sorted(found.items(), key=lambda x: -x[1])]


def check_render() -> tuple[list[str], list[str], list[str], int]:
    """앱을 실제로 렌더해 예외·제거 예정 API·라이브러리 경고를 수집."""
    from streamlit.testing.v1 import AppTest

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        at = AppTest.from_file(APP, default_timeout=120)
        at.run()

    log = buf.getvalue()
    exceptions = [str(e.value) for e in at.exception]
    removals = _uniq([r"[^\n]*will be removed[^\n]*"], log)
    futures = _uniq([r"[^\n]*FutureWarning[^\n]*",
                     r"[^\n]*DeprecationWarning[^\n]*"], log)
    return exceptions, removals, futures, len(at.tabs)


def main() -> int:
    failed = False

    print("1. 앱 렌더 검사")
    exceptions, removals, futures, tabs = check_render()
    if exceptions:
        failed = True
        print(f"   🚨 렌더 예외 {len(exceptions)}건")
        for e in exceptions:
            print(f"      {e}")
    else:
        print(f"   ✅ 예외 없음 (탭 {tabs}개 렌더 성공)")

    print("\n2. 제거 예정 API 검사")
    if removals:
        failed = True
        print(f"   🚨 {len(removals)}종 — Streamlit 버전이 오르면 죽습니다")
        for r in removals:
            print(f"      {r}")
    else:
        print("   ✅ 없음")

    print("\n3. 라이브러리 경고 (실패로 치지 않음)")
    if futures:
        print(f"   ⚠️ {len(futures)}종 — 당장 죽지는 않지만 동작이 조용히 바뀔 수 있습니다")
        for f in futures:
            print(f"      {f}")
    else:
        print("   ✅ 없음")

    print()
    if failed:
        print("❌ 실패 — 배포하면 사이트가 죽습니다. 위 항목을 고치세요.")
        return 1
    print("✅ 통과 — 배포해도 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
