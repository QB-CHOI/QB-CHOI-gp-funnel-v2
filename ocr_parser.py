"""
OCR 파서 — Tesseract 공간 매칭 기반 (주) + EasyOCR 선택적 보조
Streamlit Cloud 기본 스택: Tesseract (packages.txt 설치)
"""
import re
from PIL import Image
from difflib import SequenceMatcher

_easyocr_reader = None


def extract_from_image(image: Image.Image, rooms: dict = None) -> list:
    """
    이미지에서 채팅방 인원 추출.
    1차: Tesseract image_to_data (공간 매칭)  ← 항상 사용 가능
    2차: EasyOCR (설치된 경우만)
    """
    errors = []

    # ── 1차: Tesseract ─────────────────────────────────────────
    try:
        blocks = _blocks_from_tesseract(image)
        if blocks:
            result = _match_spatial(blocks, rooms) if rooms else _parse_blocks_numbers(blocks)
            if result:
                return result
    except Exception as e:
        errors.append(f"Tesseract: {e}")

    # ── 2차: EasyOCR (선택적) ──────────────────────────────────
    try:
        blocks = _blocks_from_easyocr(image)
        if blocks:
            result = _match_spatial(blocks, rooms) if rooms else _parse_blocks_numbers(blocks)
            if result:
                return result
    except Exception as e:
        errors.append(f"EasyOCR: {e}")

    if errors:
        raise RuntimeError(" | ".join(errors))
    return []


# ── Tesseract 블록 추출 ────────────────────────────────────────

def _blocks_from_tesseract(image: Image.Image) -> list:
    """pytesseract.image_to_data 로 바운딩박스 포함 블록 추출."""
    import pytesseract
    from pytesseract import Output
    from image_processor import preprocess_for_ocr

    # 전처리 + 원본 모두 시도하여 더 많은 블록 수집
    results = []
    for img in [preprocess_for_ocr(image), image.convert('RGB')]:
        data = pytesseract.image_to_data(
            img,
            lang='kor+eng',
            output_type=Output.DICT,
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
            cx = x + w / 2
            cy = y + h / 2
            results.append((cy, cx, text))

    # 중복 제거 (같은 위치 ±5px)
    return _deduplicate_blocks(results)


# ── EasyOCR 블록 추출 (선택적) ────────────────────────────────

def _blocks_from_easyocr(image: Image.Image) -> list:
    global _easyocr_reader
    import numpy as np
    import easyocr  # ImportError 발생하면 호출부에서 캐치

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


# ── 공간 매칭 (두 엔진 공통) ──────────────────────────────────

def _match_spatial(blocks: list, rooms: dict) -> list:
    """방 이름 블록을 찾고 같은 행의 숫자를 인원으로 매칭."""
    # 숫자 블록 추출 (1~9999)
    num_blocks = []
    for cy, cx, text in blocks:
        clean = re.sub(r'[,.\s]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 1 <= n <= 9999:
                num_blocks.append((cy, cx, n))

    if not num_blocks:
        return []

    # y 허용 범위: 이미지 전체 높이의 3%, 최소 25px
    all_y = [cy for cy, _, _ in blocks]
    y_range = max(all_y) - min(all_y) if len(all_y) > 1 else 200
    y_tol = max(25, y_range * 0.03)

    results = {}
    for room_num, room_name in rooms.items():
        best_ratio = 0.30
        best_pos = None

        for cy, cx, text in blocks:
            r = SequenceMatcher(None, room_name, text).ratio()
            # 긴 방 이름의 부분 일치도 허용
            if len(room_name) >= 4 and len(text) >= 2:
                r = max(r, _partial_ratio(room_name, text))
            if r > best_ratio:
                best_ratio = r
                best_pos = (cy, cx)

        if best_pos is None:
            continue

        ref_y, _ = best_pos
        # 같은 행의 숫자 후보 (y 허용 범위 내, 2배까지 확장 재시도)
        for tol in (y_tol, y_tol * 2):
            cands = [
                (abs(cy - ref_y), cx, n)
                for cy, cx, n in num_blocks
                if abs(cy - ref_y) <= tol
            ]
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
    """rooms 미지정 시 숫자만 순서대로 반환."""
    nums = []
    for _, _, text in blocks:
        clean = re.sub(r'[,.\s]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 1 <= n <= 9999:
                nums.append(n)
    return [{'room_num': i + 1, 'members': n} for i, n in enumerate(nums)]


def _deduplicate_blocks(blocks: list, tol: float = 5.0) -> list:
    """같은 위치(±tol px)의 중복 블록 제거."""
    seen = []
    for cy, cx, text in blocks:
        dup = any(abs(cy - sy) < tol and abs(cx - sx) < tol for sy, sx, _ in seen)
        if not dup:
            seen.append((cy, cx, text))
    return seen


def parse_from_text(raw_text: str) -> list:
    """수동 텍스트 입력용."""
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
