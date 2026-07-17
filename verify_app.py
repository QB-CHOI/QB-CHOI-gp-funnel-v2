"""배포 전 앱 렌더 검증.

실행: python3 verify_app.py

Streamlit Cloud는 push하면 바로 배포되므로, 터지는 코드를 올리면
사이트가 죽는다. 이 스크립트는 과거에 실제로 사이트를 죽였던 유형의
오류를 배포 전에 잡는다.

  1. 중첩 expander    — Streamlit이 금지. 탭 전체가 예외로 죽음
  2. 렌더 예외         — 8개 탭을 실제로 그려보고 예외 확인
  3. deprecation 경고  — 제거 예정 API. Streamlit 버전이 오르면 죽음
"""
import ast
import contextlib
import io
import re
import sys

APP = "app.py"


def check_nested_expanders() -> list[str]:
    """expander 안의 expander를 찾는다. Streamlit이 금지하는 패턴."""
    src = open(APP, encoding="utf-8").read().split("\n")
    spots = [
        (i, len(l) - len(l.lstrip()), l.strip()[:60])
        for i, l in enumerate(src, 1)
        if re.search(r"\bst\.expander\(", l)
    ]

    problems = []
    for idx, (ln, ind, txt) in enumerate(spots):
        for ln2, ind2, txt2 in spots[idx + 1 :]:
            if ind2 <= ind:
                break
            # 사이에 들여쓰기가 바깥 expander 이하로 떨어지면 블록을 벗어난 것
            escaped = any(
                l.strip()
                and not l.strip().startswith("#")
                and (len(l) - len(l.lstrip())) <= ind
                for l in src[ln : ln2 - 1]
            )
            if not escaped:
                problems.append(f"L{ln} `{txt}` 안에 L{ln2} `{txt2}`")
    return problems


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

    print("1. 중첩 expander 검사")
    nested = check_nested_expanders()
    if nested:
        failed = True
        print("   🚨 중첩 expander — 해당 탭이 통째로 죽습니다")
        for p in nested:
            print(f"      {p}")
        print("      → st.container(border=True) 로 바꾸세요")
    else:
        print("   ✅ 없음")

    print("\n2. 앱 렌더 검사")
    exceptions, deprecations, tabs = check_render()
    if exceptions:
        failed = True
        print(f"   🚨 렌더 예외 {len(exceptions)}건")
        for e in exceptions:
            print(f"      {e}")
    else:
        print(f"   ✅ 예외 없음 (탭 {tabs}개 렌더 성공)")

    print("\n3. deprecation 경고 검사")
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
