"""배포 전 앱 렌더 검증.

실행: python3 verify_app.py

Streamlit Cloud는 push하면 바로 배포되므로, 터지는 코드를 올리면
사이트가 죽는다. 이 스크립트는 실제로 사이트를 죽였던 유형의 오류를
배포 전에 잡는다.

  1. 렌더 예외        — 8개 탭을 실제로 그려보고 예외 확인
                        (예: plotly add_vline TypeError로 추이 탭 전체가 죽었던 건)
  2. deprecation 경고 — 제거 예정 API. Streamlit 버전이 오르면 죽음
                        (예: use_container_width, 제거 예정일 2025-12-31)
"""
import contextlib
import io
import re
import sys

APP = "app.py"


def check_render() -> tuple[list[str], int, int]:
    """앱을 실제로 렌더해 예외와 deprecation 경고를 수집."""
    from streamlit.testing.v1 import AppTest

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        at = AppTest.from_file(APP, default_timeout=120)
        at.run()

    log = buf.getvalue()
    exceptions = [str(e.value) for e in at.exception]
    deprecations = len(re.findall(r"will be removed after", log))
    return exceptions, deprecations, len(at.tabs)


def main() -> int:
    failed = False

    print("1. 앱 렌더 검사")
    exceptions, deprecations, tabs = check_render()
    if exceptions:
        failed = True
        print(f"   🚨 렌더 예외 {len(exceptions)}건")
        for e in exceptions:
            print(f"      {e}")
    else:
        print(f"   ✅ 예외 없음 (탭 {tabs}개 렌더 성공)")

    print("\n2. deprecation 경고 검사")
    if deprecations:
        failed = True
        print(f"   🚨 {deprecations}건 — Streamlit 버전이 오르면 죽습니다")
        print("      → 위 렌더 로그의 안내대로 교체하세요")
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
