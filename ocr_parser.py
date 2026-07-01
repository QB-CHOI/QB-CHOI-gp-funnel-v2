"""
OCR 파서 — 전략 (병렬 실행 후 병합):
A. 배지 Y 매칭 : 좌측 배지 번호 + 우측 인원(40~76%) Y좌표 매칭 — 한글 불필요
B. 텍스트 패턴 : 전체 이미지 텍스트 OCR → '채팅방 N' 패턴
→ 두 방법 병합: 배지 기반 우선, 텍스트가 합리적이면 텍스트로 교정
"""
import re
from collections import defaultdict
from PIL import Image
from difflib import SequenceMatcher

_easyocr_reader = None


# ── 메인 진입점 ────────────────────────────────────────────────────

def extract_from_image(image: Image.Image, rooms: dict = None) -> list:
    badge_results = {}
    text_results  = {}

    # A. 배지 Y 매칭 (한글 인식 불필요)
    try:
        for item in _extract_by_badge_matching(image, rooms):
            badge_results[item['room_num']] = item['members']
    except Exception:
        pass

    # B. 텍스트 패턴
    try:
        for item in _extract_by_text_pattern(image, rooms):
            text_results[item['room_num']] = item['members']
    except Exception:
        pass

    # ── 병합 ──────────────────────────────────────────────────────
    # 배지 매칭을 기본값으로, 텍스트가 50 이상이면 텍스트 우선
    # (텍스트가 22 같은 서브카테고리 오염값이면 배지 값 사용)
    results = {}
    all_found = set(list(badge_results.keys()) + list(text_results.keys()))

    for rn in all_found:
        bv = badge_results.get(rn)
        tv = text_results.get(rn)
        if bv is None:
            results[rn] = tv
        elif tv is None:
            results[rn] = bv
        elif tv >= 50:
            results[rn] = tv   # 텍스트 값이 충분히 크면 신뢰
        elif bv > tv:
            results[rn] = bv   # 텍스트가 작고 배지 값이 더 크면 배지 우선
        else:
            results[rn] = tv

    # C. 오른쪽 크롭 위치 기반 (보완)
    if rooms and len(results) < len(rooms):
        try:
            r3 = _extract_right_column(image, rooms, already_found=set(results.keys()))
            for item in r3:
                if item['room_num'] not in results:
                    results[item['room_num']] = item['members']
        except Exception:
            pass

    # D. 공간 매칭 (최후 수단)
    if rooms and len(results) < len(rooms):
        try:
            blocks = _blocks_from_tesseract(image)
            if blocks:
                r4 = _match_spatial(blocks, rooms)
                for item in r4:
                    if item['room_num'] not in results:
                        results[item['room_num']] = item['members']
        except Exception:
            pass

    if results:
        return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]
    return []


# ── A. 배지 Y 매칭 ─────────────────────────────────────────────────

def _extract_by_badge_matching(image: Image.Image, rooms: dict = None) -> list:
    """
    카카오톡 오픈채팅 목록 구조:
      [배지 0~12%]  [방이름+인원 12~76%]  [타임스탬프 78~95%]

    좌측 배지(0~15%)에서 채팅방 번호·Y위치를 읽고,
    우측 인원 구역(40~76%)에서 각 Y행의 가장 오른쪽 숫자(인원)를 읽어 매칭.

    - 타임스탬프는 78%+ 이므로 76% 크롭으로 완전 제외
    - 서브카테고리 "(타로2)" 의 '2'는 인원 '1166' 보다 왼쪽 → 오른쪽 선택 시 배제
    - 한글 전혀 불필요
    """
    import pytesseract
    from pytesseract import Output
    from image_processor import preprocess_for_ocr, preprocess_badge_region

    w, h = image.size
    cfg = '--oem 3 --psm 11 -c tessedit_char_whitelist=0123456789'

    # ── 좌측 배지 영역 (0~15%) — 3× 업스케일로 작은 배지 숫자 인식률 향상 ──
    left = image.crop((0, 0, int(w * 0.15), h))
    left_proc = preprocess_badge_region(left)

    badges = {}   # room_num → y_center (in upscaled left-crop coords)
    seen_ys = []

    for proc in [left_proc, left.convert('RGB')]:
        data = pytesseract.image_to_data(proc, output_type=Output.DICT, config=cfg)
        for i in range(len(data['text'])):
            t = str(data['text'][i]).strip()
            if not t or not t.isdigit():
                continue
            try:
                conf = int(data['conf'][i])
            except (ValueError, TypeError):
                conf = 0
            if conf < 25:
                continue
            n = int(t)
            # rooms 없이 신규 방 탐지 시: 10 미만은 배지 분리읽기 오인식으로 간주
            min_n = min(rooms.keys()) - 5 if rooms else 10
            if not (min_n <= n <= 99):
                continue
            if rooms and n not in rooms:
                continue
            cy = int(data['top'][i] + data['height'][i] / 2)
            if any(abs(cy - sy) < 20 for sy in seen_ys):
                continue
            seen_ys.append(cy)
            if n not in badges:
                badges[n] = cy

    if not badges:
        return []

    # ── 우측 인원 구역 (40~76%) ────────────────────────────────────
    # 크롭 좌표는 원본 기준이지만, preprocess_for_ocr 2x 업스케일 후
    # image_to_data 좌표는 업스케일 공간 기준 → 좌측과 동일 배율이므로 비교 가능
    rx0 = int(w * 0.40)
    rx1 = int(w * 0.76)
    right = image.crop((rx0, 0, rx1, h))
    right_proc = preprocess_for_ocr(right)

    # Y행 그룹 → 해당 행에서 가장 오른쪽 숫자
    # row_dict[y_bucket] = (cx_max, value)
    row_dict = {}

    for proc in [right_proc, right.convert('RGB')]:
        data = pytesseract.image_to_data(proc, output_type=Output.DICT, config=cfg)
        for i in range(len(data['text'])):
            t = str(data['text'][i]).strip()
            if not t or not t.isdigit():
                continue
            try:
                conf = int(data['conf'][i])
            except (ValueError, TypeError):
                conf = 0
            if conf < 20:
                continue
            n = int(t)
            if not (1 <= n <= 99999):
                continue
            cy = int(data['top'][i] + data['height'][i] / 2)
            cx = int(data['left'][i] + data['width'][i] / 2)
            # 15px 단위 Y 버킷 (업스케일 좌표 기준)
            y_bucket = round(cy / 15) * 15
            if y_bucket not in row_dict or cx > row_dict[y_bucket][0]:
                row_dict[y_bucket] = (cx, n)

    if not row_dict:
        return []

    member_rows = [(yb, val) for yb, (_, val) in row_dict.items()]

    # ── Y 위치 매칭 ────────────────────────────────────────────────
    row_height = h / max(len(badges), 5)
    # 업스케일 2x → 배지 Y도 업스케일 기준이므로 row_height도 2x
    row_height_scaled = row_height * 2
    results = []
    used_ybs = set()

    for room_num, badge_y in sorted(badges.items(), key=lambda x: x[1]):
        cands = [(abs(yb - badge_y), yb, val)
                 for yb, val in member_rows
                 if abs(yb - badge_y) < row_height_scaled * 0.7
                 and yb not in used_ybs]
        if not cands:
            continue
        cands.sort()
        _, yb, val = cands[0]
        results.append({'room_num': room_num, 'members': val})
        used_ybs.add(yb)

    return results


# ── B. 텍스트 패턴 ─────────────────────────────────────────────────

def _extract_by_text_pattern(image: Image.Image, rooms: dict = None) -> list:
    """전체 이미지 텍스트 OCR → '채팅방 N' 패턴으로 인원 추출."""
    import pytesseract
    from image_processor import preprocess_for_ocr

    texts = []
    for proc_img in [preprocess_for_ocr(image), image.convert('RGB')]:
        for cfg in ['--oem 3 --psm 6', '--oem 3 --psm 11']:
            try:
                t = pytesseract.image_to_string(proc_img, lang='kor+eng', config=cfg)
                if t.strip():
                    texts.append(t)
            except Exception:
                pass

    results = {}
    for text in texts:
        for item in _parse_chatroom_text(text, rooms):
            rn = item['room_num']
            if rn not in results:
                results[rn] = item['members']
        if rooms and len(results) >= len(rooms):
            break

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def _parse_chatroom_text(raw_text: str, rooms: dict = None) -> list:
    """
    텍스트에서 채팅방 번호와 인원 수를 추출.
    카카오톡 행 구조: [채팅방명 + 인원] [타임스탬프]
    → 인원은 채팅방 번호 직후 첫 번째 숫자, 타임스탬프는 마지막 숫자.
    """
    results = {}
    for line in raw_text.strip().splitlines():
        m = re.search(r'채팅방\s*(\d{1,3})', line)
        if not m:
            continue
        rn = int(m.group(1))
        if rooms and rn not in rooms:
            continue
        if rn in results:
            continue

        after = line[m.end():]
        after_clean = re.sub(r'\([^)]*\)', ' ', after)   # (사주2) 제거
        after_clean = re.sub(r'번', ' ', after_clean)     # '번' 제거
        after_clean = re.sub(r'[가-힣]+', ' ', after_clean)  # 한글 제거 (오전/오후 등)

        raw_nums = re.findall(r'\d{1,3}(?:,\d{3})+|\d+', after_clean)
        nums = [int(n.replace(',', '')) for n in raw_nums]
        valid = [n for n in nums if 1 <= n <= 99999]

        if valid:
            results[rn] = valid[0]  # 첫 번째 = 인원 (타임스탬프는 뒤에 위치)

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


# ── C. 오른쪽 크롭 위치 기반 ──────────────────────────────────────

def _extract_right_column(image: Image.Image, rooms: dict = None,
                           already_found: set = None) -> list:
    """40%부터 크롭 후 Y 순서 기반 매핑 (보완용)."""
    import pytesseract
    from image_processor import preprocess_for_ocr

    if already_found is None:
        already_found = set()

    w, h = image.size
    # 76% 우측 경계 — 배지 매칭과 동일하게 타임스탬프 구역(78%~) 제외
    right = image.crop((int(w * 0.40), 0, int(w * 0.76), h))
    right_proc = preprocess_for_ocr(right)

    configs = [
        '--oem 3 --psm 11 -c tessedit_char_whitelist=0123456789,.',
        '--oem 3 --psm 6  -c tessedit_char_whitelist=0123456789,.',
    ]

    numbers = []
    seen_y = set()

    for cfg in configs:
        from pytesseract import Output
        data = pytesseract.image_to_data(right_proc, lang='kor+eng',
                                         output_type=Output.DICT, config=cfg)
        for i in range(len(data['text'])):
            text = str(data['text'][i]).strip()
            if not text:
                continue
            try:
                conf = int(data['conf'][i])
            except (ValueError, TypeError):
                conf = 0
            if conf < 20:
                continue
            clean = re.sub(r'[,.\s]', '', text)
            if not clean.isdigit():
                continue
            n = int(clean)
            if not (5 <= n <= 99999):
                continue
            cy = int(data['top'][i] + data['height'][i] / 2)
            if any(abs(cy - sy) < 15 for sy in seen_y):
                continue
            seen_y.add(cy)
            numbers.append((cy, n))

    if not numbers:
        return []

    numbers.sort(key=lambda x: x[0])

    if not rooms:
        return [{'room_num': i + 1, 'members': v} for i, (_, v) in enumerate(numbers)]

    missing_keys = [k for k in sorted(rooms.keys()) if k not in already_found]
    return [{'room_num': missing_keys[idx], 'members': val}
            for idx, (_, val) in enumerate(numbers) if idx < len(missing_keys)]


# ── D. Tesseract 블록 추출 ─────────────────────────────────────────

def _blocks_from_tesseract(image: Image.Image) -> list:
    import pytesseract
    from pytesseract import Output
    from image_processor import preprocess_for_ocr

    results = []
    for img in [preprocess_for_ocr(image), image.convert('RGB')]:
        data = pytesseract.image_to_data(
            img, lang='kor+eng', output_type=Output.DICT,
            config='--oem 3 --psm 11',
        )
        for i in range(len(data['text'])):
            text = str(data['text'][i]).strip()
            if not text:
                continue
            try:
                conf = int(data['conf'][i])
            except (ValueError, TypeError):
                conf = 0
            if conf < 20:
                continue
            x = int(data['left'][i])
            y = int(data['top'][i])
            bw = int(data['width'][i])
            bh = int(data['height'][i])
            results.append((y + bh / 2, x + bw / 2, text))

    return _deduplicate_blocks(results)


# ── 공간 매칭 ─────────────────────────────────────────────────────

def _match_spatial(blocks: list, rooms: dict) -> list:
    num_blocks = []
    for cy, cx, text in blocks:
        clean = re.sub(r'[,.\s]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 1 <= n <= 99999:
                num_blocks.append((cy, cx, n))

    if not num_blocks:
        return []

    all_y = [cy for cy, _, _ in blocks]
    y_range = max(all_y) - min(all_y) if len(all_y) > 1 else 200
    y_tol = max(25, y_range * 0.03)

    results = {}
    for room_num, room_name in rooms.items():
        best_ratio = 0.30
        best_pos = None
        for cy, cx, text in blocks:
            r = SequenceMatcher(None, room_name, text).ratio()
            if len(room_name) >= 4 and len(text) >= 2:
                r = max(r, _partial_ratio(room_name, text))
            if r > best_ratio:
                best_ratio = r
                best_pos = (cy, cx)

        if best_pos is None:
            continue

        ref_y, _ = best_pos
        for tol in (y_tol, y_tol * 2):
            cands = [(abs(cy - ref_y), cx, n) for cy, cx, n in num_blocks
                     if abs(cy - ref_y) <= tol]
            if cands:
                cands.sort()
                results[room_num] = cands[0][2]
                break

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def _partial_ratio(a: str, b: str) -> float:
    if len(b) > len(a):
        a, b = b, a
    best = 0.0
    step = max(1, len(b) // 2)
    for i in range(0, len(a) - len(b) + 1, step):
        r = SequenceMatcher(None, a[i:i + len(b)], b).ratio()
        if r > best:
            best = r
    return best


def _deduplicate_blocks(blocks: list, tol: float = 5.0) -> list:
    seen = []
    for cy, cx, text in blocks:
        dup = any(abs(cy - sy) < tol and abs(cx - sx) < tol for sy, sx, _ in seen)
        if not dup:
            seen.append((cy, cx, text))
    return seen


def get_badge_rooms(image: Image.Image) -> dict:
    """
    배지 영역(0~15%)에서만 채팅방을 탐지 → {room_num: members} 반환.
    한글·미리보기 텍스트와 무관하므로 신규 방 탐지 시 오인식 최소화.
    """
    try:
        results = _extract_by_badge_matching(image, None)
        return {item['room_num']: item['members'] for item in results}
    except Exception:
        return {}


def parse_from_text(raw_text: str) -> list:
    """외부 호출용 텍스트 기반 파싱."""
    results = {}
    for line in raw_text.strip().splitlines():
        m = re.search(r'채팅방\s*(\d{1,3})', line)
        if not m:
            continue
        rn = int(m.group(1))
        if rn in results:
            continue
        after = line[m.end():]
        after_clean = re.sub(r'\([^)]*\)', ' ', after)
        after_clean = re.sub(r'번', ' ', after_clean)
        after_clean = re.sub(r'[가-힣]+', ' ', after_clean)
        raw_nums = re.findall(r'\d{1,3}(?:,\d{3})+|\d+', after_clean)
        nums = [int(n.replace(',', '')) for n in raw_nums]
        valid = [n for n in nums if 1 <= n <= 99999]
        if valid:
            results[rn] = valid[0]
    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]
