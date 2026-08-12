"""데이터 자동 갱신 — launchd가 매일 호출하는 진입점.

네 가지를 순서대로 처리한다. 어느 하나가 실패해도 나머지는 계속 진행한다.

  1) 시장 신호   : 키워드 분석툴 캐시 → market_signals.csv   (매일 자동)
  2) 주문 집계   : 새 '강의별_리스트*.xlsx'가 있을 때만 15종 재생성
  3) 오행 집계   : 위 2)가 돌았을 때만 함께 갱신
  4) 오카방 방목록: '오카방의 모든 것.xlsx' → campaigns.csv  (매일 자동)

설계 원칙
  · **내용이 같으면 푸시하지 않는다** — 매일 도는 작업이라 동일 커밋이
    쌓이면 이력이 지저분해지고 API 호출만 낭비된다.
  · 주문 엑셀은 사람이 아임웹에서 내려받아야 하므로 자동화할 수 없다.
    대신 ~/Downloads에 새 파일이 생기면 자동으로 알아채 반영한다.
  · 구글 드라이브도 직접 못 읽는다(서비스 계정·rclone·드라이브 데스크톱 없음).
    4)는 **로컬에 내려온 사본**을 읽는다 — 드라이브 데스크톱을 깔면 그 경로가
    자동으로 잡히고, 그 전까지는 inbox/에 둔 사본을 쓴다.
  · 실패해도 조용히 죽지 않고 로그에 남긴다(launchd는 화면이 없다).

실행:
    python3 scripts/auto_refresh.py            # 전체
    python3 scripts/auto_refresh.py --dry-run  # 확인만, 쓰지 않음
"""
import argparse
import glob
import hashlib
import io
import json
import os
import sys
import traceback
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

STATE_PATH = os.path.join(ROOT, ".auto_refresh_state.json")

# 주문 엑셀을 찾는 위치(순서대로). inbox가 먼저인 이유:
# macOS는 Downloads·Documents·Desktop을 TCC로 보호해서 launchd가 읽지 못한다.
# 프로젝트 안 inbox/는 보호 대상이 아니라 권한 설정 없이도 동작한다.
INBOX = os.path.join(ROOT, "inbox")
ORDER_PATTERNS = [
    os.path.join(INBOX, "강의별_리스트*.xlsx"),
    os.path.expanduser("~/Downloads/강의별_리스트*.xlsx"),
]


def find_order_files(patterns=None):
    """주문 엑셀 찾기 — macOS 한글 파일명 정규화(NFD) 대응.

    macOS는 파일명을 NFD(자모 분리)로 저장하는데 소스의 문자열 리터럴은
    NFC라서 glob이 그냥은 매칭되지 않는다. 두 형태를 모두 시도한다.
    """
    import unicodedata
    found = []
    for pattern in (patterns or ORDER_PATTERNS):
        for pat in (pattern,
                    unicodedata.normalize("NFD", pattern),
                    unicodedata.normalize("NFC", pattern)):
            try:
                hits = glob.glob(pat)
            except OSError:
                continue
            for f in hits:
                if f not in found:
                    found.append(f)
    return sorted(found, key=os.path.getmtime)


FDA_HELP = (
    "macOS 보호 폴더(Documents·Downloads)는 자동 실행 프로세스가 읽지 못합니다.\n"
    "     해결 A) 주문 엑셀을 gp-funnel-v2/inbox/ 에 두면 권한 없이 동작합니다.\n"
    "     해결 B) 시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한에\n"
    "            /usr/bin/python3 을 추가하면 원래 위치도 읽습니다."
)


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def _state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(s):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except OSError as e:
        log(f"  ⚠️ 상태 저장 실패: {e}")


def _remote_same(path, df):
    """원격 CSV와 내용이 같은지. 같으면 푸시를 건너뛴다."""
    try:
        from github_store import _read_csv
        cur = _read_csv(path, list(df.columns))
        if cur.empty:
            return False
        a = cur.to_csv(index=False).encode()
        b = df.to_csv(index=False).encode()
        return hashlib.md5(a).hexdigest() == hashlib.md5(b).hexdigest()
    except Exception:
        return False


def _push(path, df, message, dry):
    if _remote_same(path, df):
        log(f"  · {path} 변경 없음 — 건너뜀")
        return False
    if dry:
        log(f"  · [dry-run] {path} 갱신 예정 ({len(df)}행)")
        return True
    from github_store import _write_csv
    _write_csv(path, df, message)
    log(f"  ✅ {path} 갱신 ({len(df)}행)")
    return True


# ── 1) 시장 신호 ─────────────────────────────────────────────
def refresh_market_signals(dry):
    log("① 시장 신호 (키워드 분석툴)")
    try:
        from scripts.sync_market_signals import build, PROCESSED
    except ImportError as e:
        log(f"  ⚠️ 모듈 로드 실패: {e}")
        return False
    if not os.path.isdir(PROCESSED):
        log("  · 키워드 분석툴 데이터 없음 — 건너뜀")
        return False
    # 파일이 실제로 읽히는지 먼저 확인. macOS TCC(개인정보 보호) 때문에
    # launchd에서는 디렉터리는 보이는데 내용이 안 읽히는 경우가 있다.
    try:
        n_cache = len(os.listdir(PROCESSED))
    except PermissionError:
        log("  🔒 접근 거부 — 키워드 분석툴 캐시를 읽을 수 없습니다")
        log(f"     {FDA_HELP}")
        return False
    log(f"  · 캐시 파일 {n_cache}개 확인")
    try:
        df = build()
    except PermissionError:
        log("  🔒 파일 읽기 거부 — 권한 필요")
        log(f"     {FDA_HELP}")
        return False
    except Exception as e:
        log(f"  ⚠️ 추출 실패: {type(e).__name__}: {e}")
        return False
    if df.empty:
        log("  · 추출된 신호 없음 — 건너뜀")
        return False
    collected = df["collected"].iloc[0] if "collected" in df.columns else "?"
    return _push("data/market_signals.csv", df,
                 f"data: 시장 신호 자동 갱신 ({collected})", dry)


# ── 2)·3) 주문 원본 기반 집계 ────────────────────────────────
def refresh_order_based(dry):
    log("② 주문 집계 · ③ 오행 집계")
    files = find_order_files()
    if not files:
        log("  · 주문 엑셀 없음 — 건너뜀 (inbox/ 또는 ~/Downloads)")
        return False
    latest = files[-1]
    sig = f"{os.path.basename(latest)}|{int(os.path.getmtime(latest))}"
    st = _state()
    if st.get("order_file") == sig:
        log(f"  · 새 주문 파일 없음 ({os.path.basename(latest)}) — 건너뜀")
        return False

    log(f"  · 새 주문 파일 감지: {os.path.basename(latest)}")
    changed = False
    try:
        from scripts.refresh_order_aggregates import load_orders, build_all
        o = load_orders(latest)
        for fname, df in build_all(o).items():
            if isinstance(df, tuple):      # (df, 검증문자열) 형태 대응
                df = df[0]
            if _push(f"data/{fname}", df, f"data: 주문 집계 자동 갱신 ({fname})", dry):
                changed = True
    except Exception as e:
        log(f"  ⚠️ 주문 집계 실패: {e}")
        log(traceback.format_exc(limit=2))

    try:
        from scripts.build_ohaeng_period import build as build_oh
        from scripts.refresh_order_aggregates import load_orders as _lo
        df_oh = build_oh(_lo(latest))
        if _push("data/ohaeng_period.csv", df_oh,
                 "data: 오행 시기 집계 자동 갱신", dry):
            changed = True
    except Exception as e:
        log(f"  ⚠️ 오행 집계 실패: {e}")

    if not dry:
        st["order_file"] = sig
        st["order_refreshed_at"] = datetime.now().isoformat(timespec="seconds")
        _save_state(st)
    return changed


# ── 4) 오카방 레지스트리 ─────────────────────────────────────
def refresh_rooms(dry):
    log("④ 오카방 방목록 (구글 드라이브 시트)")
    try:
        from scripts.sync_rooms_from_drive import run
        return run(dry)
    except Exception as e:
        log(f"  ⚠️ 방목록 동기화 실패: {type(e).__name__}: {e}")
        log(traceback.format_exc(limit=2))
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="확인만, 쓰지 않음")
    a = ap.parse_args()

    log("=" * 52)
    log(f"데이터 자동 갱신 시작{' (dry-run)' if a.dry_run else ''}")
    results = []
    for fn in (refresh_market_signals, refresh_order_based, refresh_rooms):
        try:
            results.append(fn(a.dry_run))
        except Exception as e:
            log(f"  ⚠️ 예외: {e}")
            log(traceback.format_exc(limit=3))
            results.append(False)

    st = _state()
    st["last_run"] = datetime.now().isoformat(timespec="seconds")
    st["last_changed"] = any(results)
    if not a.dry_run:
        _save_state(st)
        # 실행 결과를 사이트에서도 볼 수 있게 기록.
        # (로그는 이 맥에만 있어서, 자동 갱신이 멈춰도 눈치채기 어렵다)
        try:
            from github_store import _write_csv
            _write_csv("data/refresh_status.csv", pd.DataFrame([{
                "last_run": st["last_run"],
                "market_signals": "갱신" if results[0] else "변경없음/실패",
                "order_aggregates": "갱신" if results[1] else "변경없음/실패",
                "rooms": "갱신" if results[2] else "변경없음/실패",
                "changed": "예" if any(results) else "아니오",
            }]), f"chore: 자동 갱신 상태 {st['last_run']}")
        except Exception as e:
            log(f"  ⚠️ 상태 기록 실패: {e}")
    log(f"완료 — 갱신 {'있음' if any(results) else '없음'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
