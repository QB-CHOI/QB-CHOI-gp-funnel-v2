"""
OCR 파서 — 전략 우선순위:
1. 전체 이미지 텍스트 OCR → '채팅방 N' 패턴 매칭 (가장 신뢰도 높음)
2. 오른쪽 영역 위치 기반 숫자 추출 (보조)
3. 공간 매칭 (최후 수단)
"""
import re
from PIL import Image
from difflib import SequenceMatcher

_easyocr_reader = None


def extract_from_image(image: Image.Image, rooms: dict = None) -> list:
    results = {}

    # ── 1차: 텍스트 패턴 매칭 ─────────────────────────────────────
    # "채팅방 34(사주2) 136" 같은 텍스트를 직접 파싱 → 방 번호 확실히 매핑
    try:
        r1 = _extract_by_text_pattern(image, rooms)
        for item in r1:
            results[item['room_num']] = item['members']
    except Exception:
        pass

    # ── 2차: 오른쪽 영역 위치 기반 (1차에서 미인식 방 보완) ───────
    if rooms and len(results) < len(rooms):
        try:
            r2 = _extract_right_column(image, rooms, already_found=set(results.keys()))
            for item in r2:
                if item['room_num'] not in results:
                    results[item['room_num']] = item['members']
        except Exception:
            pass

    # ── 3차: 공간 매칭 (블록 단위 텍스트 + 위치) ──────────────────
    if rooms and len(results) < len(rooms):
        try:
            blocks = _blocks_from_tesseract(image)
            if blocks:
                r3 = _match_spatial(blocks, rooms)
                for item in r3:
                    if item['room_num'] not in results:
                        results[item['room_num']] = item['members']
        except Exception:
            pass

    if results:
        return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]

    return []


# ── 1차: 텍스트 전체 파싱 ─────────────────────────────────────────

def _extract_by_text_pattern(image: Image.Image, rooms: dict = None) -> list:
    """
    전체 이미지를 텍스트로 읽고 '채팅방 N ... 숫자' 패턴으로 인원 추출.
    방 이름에 번호가 명시되어 있으므로 위치가 아닌 방 번호로 직접 매핑.
    """
    import pytesseract
    from image_processor import preprocess_for_ocr

    texts = []
    # 전처리 이미지
    try:
        proc = preprocess_for_ocr(image)
        t = pytesseract.image_to_string(proc, lang='kor+eng', config='--oem 3 --psm 6')
        if t.strip():
            texts.append(t)
    except Exception:
        pass

    # 원본 RGB (전처리가 오히려 방해될 경우)
    try:
        t2 = pytesseract.image_to_string(image.convert('RGB'), lang='kor+eng', config='--oem 3 --psm 6')
        if t2.strip():
            texts.append(t2)
    except Exception:
        pass

    # psm 11 (단어 단위)
    try:
        proc = preprocess_for_ocr(image)
        t3 = pytesseract.image_to_string(proc, lang='kor+eng', config='--oem 3 --psm 11')
        if t3.strip():
            texts.append(t3)
    except Exception:
        pass

    results = {}
    for text in texts:
        parsed = _parse_chatroom_text(text, rooms)
        for item in parsed:
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
    lines = raw_text.strip().splitlines()

    for line in lines:
        # '채팅방' 키워드가 있는 줄만 처리
        m = re.search(r'채팅방\s*(\d{1,3})', line)
        if not m:
            continue
        rn = int(m.group(1))
        if rooms and rn not in rooms:
            continue
        if rn in results:
            continue

        # 채팅방 번호 뒤 텍스트
        after = line[m.end():]
        # 괄호 안 제거: (사주2), (타로2), (부동산2) 등
        after_clean = re.sub(r'\([^)]*\)', ' ', after)
        # '번' 제거: "37번" → "37 "
        after_clean = re.sub(r'번', ' ', after_clean)
        # 한글 제거: "오전", "오후" 같은 타임스탬프 접두어 + 기타 한글 텍스트
        # → "오전 12:21" 의 "오전"을 제거해 "12:21"만 남김
        after_clean = re.sub(r'[가-힣]+', ' ', after_clean)

        # 숫자 추출 (쉼표 포함: 1,234 → 1234)
        raw_nums = re.findall(r'\d{1,3}(?:,\d{3})+|\d+', after_clean)
        nums = [int(n.replace(',', '')) for n in raw_nums]
        valid = [n for n in nums if 50 <= n <= 99999]

        if valid:
            # 첫 번째 유효 숫자 = 인원 수
            # (타임스탬프 "12:21"→"1221" 은 항상 인원 뒤에 위치)
            results[rn] = valid[0]

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


# ── 2차: 오른쪽 영역 위치 기반 ───────────────────────────────────

def _extract_right_column(image: Image.Image, rooms: dict = None,
                           already_found: set = None) -> list:
    """
    이미지 오른쪽 영역에서 세로 순서로 숫자를 읽어 방에 매핑.
    카카오톡 인원 숫자는 방이름 뒤~타임스탬프 앞에 위치.
    이미 찾은 방(already_found)은 건너뜀.
    """
    import pytesseract
    from image_processor import preprocess_for_ocr

    if already_found is None:
        already_found = set()

    w, h = image.size

    # 왼쪽 배지(~10%)를 제외하고 중간~오른쪽(40~100%) 크롭
    # 인원 숫자가 방이름 바로 뒤에 있어서 50~80% x 위치에 주로 분포
    right = image.crop((int(w * 0.40), 0, w, h))
    right_proc = preprocess_for_ocr(right)

    configs = [
        '--oem 3 --psm 11 -c tessedit_char_whitelist=0123456789,.',
        '--oem 3 --psm 6  -c tessedit_char_whitelist=0123456789,.',
    ]

    numbers = []  # (center_y, value)
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
            if not (50 <= n <= 99999):
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

    # 미인식 방만 순서 매핑
    missing_keys = [k for k in sorted(rooms.keys()) if k not in already_found]
    results = []
    for idx, (_, val) in enumerate(numbers):
        if idx < len(missing_keys):
            results.append({'room_num': missing_keys[idx], 'members': val})
    return results


# ── Tesseract 블록 추출 ────────────────────────────────────────

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


# ── EasyOCR 블록 추출 (선택적) ────────────────────────────────

def _blocks_from_easyocr(image: Image.Image) -> list:
    global _easyocr_reader
    import numpy as np
    import easyocr

    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)

    img_np = np.array(image.convert('RGB'))
    raw = _easyocr_reader.readtext(img_np, detail=1, paragraph=False)
    blocks = []
    for bbox, text, conf in raw:
        if conf < 0.25 or not text.strip():
            continue
        cx = (bbox[0][0] + bbox[2][0]) / 2
        cy = (bbox[0][1] + bbox[2][1]) / 2
        blocks.append((cy, cx, text.strip()))
    return blocks


# ── 공간 매칭 ─────────────────────────────────────────────────

def _match_spatial(blocks: list, rooms: dict) -> list:
    num_blocks = []
    for cy, cx, text in blocks:
        clean = re.sub(r'[,.\s]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 50 <= n <= 99999:
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


def _parse_blocks_numbers(blocks: list) -> list:
    nums = []
    for _, _, text in blocks:
        clean = re.sub(r'[,.\s]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 50 <= n <= 99999:
                nums.append(n)
    return [{'room_num': i + 1, 'members': n} for i, n in enumerate(nums)]


def _deduplicate_blocks(blocks: list, tol: float = 5.0) -> list:
    seen = []
    for cy, cx, text in blocks:
        dup = any(abs(cy - sy) < tol and abs(cx - sx) < tol for sy, sx, _ in seen)
        if not dup:
            seen.append((cy, cx, text))
    return seen


def parse_from_text(raw_text: str) -> list:
    """외부 호출용 텍스트 기반 파싱 (rooms 없이)."""
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
        valid = [n for n in nums if 50 <= n <= 99999]
        if valid:
            results[rn] = valid[0]
    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]
