import re
from PIL import Image
from difflib import SequenceMatcher

_easyocr_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
    return _easyocr_reader


def extract_from_image(image: Image.Image, rooms: dict = None) -> list:
    """이미지에서 채팅방 인원 추출. EasyOCR 실패 시 Tesseract로 폴백."""
    errors = []

    # 1차: EasyOCR (더 정확)
    try:
        blocks = _blocks_from_easyocr(image)
        if blocks:
            if rooms:
                result = _match_spatial(blocks, rooms)
            else:
                result = _parse_blocks_fallback(blocks)
            if result:
                return result
    except Exception as e:
        errors.append(f"EasyOCR: {e}")

    # 2차: Tesseract (같은 공간 매칭 로직)
    try:
        blocks = _blocks_from_tesseract(image)
        if blocks:
            if rooms:
                result = _match_spatial(blocks, rooms)
            else:
                result = _parse_blocks_fallback(blocks)
            if result:
                return result
    except Exception as e:
        errors.append(f"Tesseract: {e}")

    if errors:
        raise RuntimeError(" | ".join(errors))
    return []


# ── 각 OCR 엔진에서 블록 추출 ──────────────────────────────────────
# 블록 형식: (center_y, center_x, text)

def _blocks_from_easyocr(image: Image.Image) -> list:
    import numpy as np
    reader = _get_easyocr_reader()
    img_np = np.array(image.convert('RGB'))
    raw = reader.readtext(img_np, detail=1, paragraph=False)
    blocks = []
    for bbox, text, conf in raw:
        if conf < 0.3:
            continue
        text = text.strip()
        if not text:
            continue
        cx = (bbox[0][0] + bbox[2][0]) / 2
        cy = (bbox[0][1] + bbox[2][1]) / 2
        blocks.append((cy, cx, text))
    return blocks


def _blocks_from_tesseract(image: Image.Image) -> list:
    import pytesseract
    from pytesseract import Output
    from image_processor import preprocess_for_ocr

    img = preprocess_for_ocr(image)
    data = pytesseract.image_to_data(
        img,
        lang='kor+eng',
        output_type=Output.DICT,
        config='--oem 3 --psm 11',
    )

    blocks = []
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if not text:
            continue
        try:
            conf = int(data['conf'][i])
        except (ValueError, TypeError):
            conf = 0
        if conf < 30:
            continue
        x = data['left'][i]
        y = data['top'][i]
        w = data['width'][i]
        h = data['height'][i]
        cx = x + w / 2
        cy = y + h / 2
        blocks.append((cy, cx, text))
    return blocks


# ── 공간 매칭 ─────────────────────────────────────────────────────

def _match_spatial(blocks: list, rooms: dict) -> list:
    """방 이름 블록을 찾고, 같은 행의 오른쪽 숫자를 인원으로 매칭."""
    # 숫자 블록 추출 (1~9999 범위)
    num_blocks = []
    for cy, cx, text in blocks:
        clean = re.sub(r'[,. ]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 1 <= n <= 9999:
                num_blocks.append((cy, cx, n))

    # 이미지 너비 기준 y 허용 범위 동적 설정
    all_y = [cy for cy, _, _ in blocks]
    y_range = max(all_y) - min(all_y) if len(all_y) > 1 else 100
    y_tolerance = max(30, y_range * 0.03)  # 전체 높이의 3%, 최소 30px

    results = {}
    for room_num, room_name in rooms.items():
        # 방 이름과 가장 유사한 블록 찾기
        best_ratio = 0.35
        best_pos = None
        for cy, cx, text in blocks:
            # 방 이름 전체 또는 부분 포함 여부
            ratio = SequenceMatcher(None, room_name, text).ratio()
            # 방 이름이 긴 경우 부분 문자열 매칭도 시도
            if len(room_name) >= 4 and len(text) >= 2:
                ratio = max(ratio, _partial_ratio(room_name, text))
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = (cy, cx)

        if best_pos is None:
            continue

        ref_y, ref_x = best_pos
        candidates = [
            (abs(cy - ref_y), abs(cx - ref_x), n)
            for cy, cx, n in num_blocks
            if abs(cy - ref_y) <= y_tolerance
        ]
        if not candidates:
            # y 허용 범위를 늘려서 재시도
            candidates = [
                (abs(cy - ref_y), abs(cx - ref_x), n)
                for cy, cx, n in num_blocks
                if abs(cy - ref_y) <= y_tolerance * 2
            ]

        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]))
            results[room_num] = candidates[0][2]

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def _partial_ratio(a: str, b: str) -> float:
    """b가 a의 부분 문자열인지 유사도 계산."""
    if len(b) > len(a):
        a, b = b, a
    best = 0.0
    for i in range(len(a) - len(b) + 1):
        sub = a[i:i + len(b)]
        r = SequenceMatcher(None, sub, b).ratio()
        if r > best:
            best = r
    return best


def _parse_blocks_fallback(blocks: list) -> list:
    """rooms 미지정 시 — 숫자만 추출하여 순서대로 반환 (방 번호 미지정)."""
    nums = []
    for _, _, text in blocks:
        clean = re.sub(r'[,. ]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 1 <= n <= 9999:
                nums.append(n)
    return [{'room_num': i + 1, 'members': n} for i, n in enumerate(nums)]


def parse_from_text(raw_text: str) -> list:
    """텍스트 직접 파싱 (수동 입력용)."""
    results = {}
    for line in raw_text.strip().splitlines():
        room_match = re.search(r'채팅방\s*(\d{1,3})', line)
        if not room_match:
            continue
        room_num = int(room_match.group(1))
        if room_num in results:
            continue
        after = line[room_match.end():]
        after = re.sub(r'^번', '', after)
        nums = re.findall(r'\b(\d{1,3}(?:,\d{3})*|\d{1,4})\b', after)
        valid = [int(n.replace(',', '')) for n in nums if 1 <= int(n.replace(',', '')) <= 9999]
        if valid:
            results[room_num] = valid[0]
    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]
