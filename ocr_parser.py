"""
OCR 파서 — Tesseract 위치 기반 숫자 추출 (메인) + EasyOCR 선택적 보조
Streamlit Cloud 기본 스택: Tesseract (packages.txt 설치)
"""
import re
from PIL import Image
from difflib import SequenceMatcher

_easyocr_reader = None


def extract_from_image(image: Image.Image, rooms: dict = None) -> list:
    """
    이미지에서 채팅방 인원 추출.
    1차: 오른쪽 영역 위치 기반 숫자 추출 (Tesseract)
    2차: 전체 이미지 공간 매칭 (Tesseract)
    """
    # 1차: 오른쪽 영역 집중 추출 (방 이름 매칭 불필요)
    try:
        result = _extract_right_column(image, rooms)
        if result:
            return result
    except Exception:
        pass

    # 2차: 전체 이미지 텍스트 블록 공간 매칭
    try:
        blocks = _blocks_from_tesseract(image)
        if blocks and rooms:
            result = _match_spatial(blocks, rooms)
            if result:
                return result
        elif blocks:
            return _parse_blocks_numbers(blocks)
    except Exception:
        pass

    return []


def _extract_right_column(image: Image.Image, rooms: dict = None) -> list:
    """
    카카오톡 채팅 목록 오른쪽에 표시되는 인원 수 추출.
    이미지 오른쪽 30% 영역에서 숫자를 세로 순서대로 읽어 방에 매핑.
    """
    import pytesseract
    from image_processor import preprocess_for_ocr

    w, h = image.size

    # 오른쪽 30% + 전처리
    right = image.crop((int(w * 0.70), 0, w, h))
    right_proc = preprocess_for_ocr(right)

    # 숫자 전용 설정으로 추출
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
            if not (1 <= n <= 9999):
                continue
            cy = int(data['top'][i] + data['height'][i] / 2)
            # 같은 Y 위치(±15px) 중복 제거
            if any(abs(cy - sy) < 15 for sy in seen_y):
                continue
            seen_y.add(cy)
            numbers.append((cy, n))

    if not numbers:
        return []

    numbers.sort(key=lambda x: x[0])  # 위→아래 정렬

    if rooms:
        room_keys = sorted(rooms.keys())
        results = []
        for idx, (_, val) in enumerate(numbers):
            if idx < len(room_keys):
                results.append({'room_num': room_keys[idx], 'members': val})
        return results
    else:
        return [{'room_num': i + 1, 'members': v} for i, (_, v) in enumerate(numbers)]


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
            w = int(data['width'][i])
            h = int(data['height'][i])
            results.append((y + h / 2, x + w / 2, text))

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
            if 1 <= n <= 9999:
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
            if 1 <= n <= 9999:
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
    results = {}
    for line in raw_text.strip().splitlines():
        m = re.search(r'채팅방\s*(\d{1,3})', line)
        if not m:
            continue
        rn = int(m.group(1))
        if rn in results:
            continue
        after = re.sub(r'^번', '', line[m.end():])
        nums = re.findall(r'\b(\d{1,3}(?:,\d{3})*|\d{1,4})\b', after)
        valid = [int(n.replace(',', '')) for n in nums if 1 <= int(n.replace(',', '')) <= 9999]
        if valid:
            results[rn] = valid[0]
    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]
