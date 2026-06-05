import re
from PIL import Image

# 모듈 레벨 캐시 — 최초 1회만 모델 로드
_easyocr_reader = None


def _get_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
    return _easyocr_reader


def extract_from_image(image: Image.Image, rooms: dict = None) -> list:
    """이미지에서 채팅방 인원 추출.
    rooms: {room_num: room_name} — 있으면 방 이름 기반 공간 매칭 수행.
    """
    try:
        return _extract_easyocr(image, rooms)
    except Exception:
        return _extract_tesseract(image)


def _extract_easyocr(image: Image.Image, rooms: dict = None) -> list:
    import numpy as np
    reader = _get_reader()
    img_np = np.array(image.convert('RGB'))
    raw = reader.readtext(img_np, detail=1, paragraph=False)
    # raw: [(bbox, text, confidence), ...]

    if rooms:
        return _match_spatial(raw, rooms)
    return _parse_easyocr_text(raw)


def _match_spatial(raw: list, rooms: dict) -> list:
    """바운딩박스 위치 기반으로 방 이름 근처 숫자를 인원으로 매칭."""
    from difflib import SequenceMatcher

    # 텍스트 블록 리스트: (center_y, center_x, text)
    blocks = []
    for bbox, text, _ in raw:
        cx = (bbox[0][0] + bbox[2][0]) / 2
        cy = (bbox[0][1] + bbox[2][1]) / 2
        blocks.append((cy, cx, text.strip()))

    # 숫자 블록만 추출 (콤마·점 제거 후 1~9999)
    num_blocks = []
    for cy, cx, text in blocks:
        clean = re.sub(r'[,.]', '', text)
        if clean.isdigit():
            n = int(clean)
            if 1 <= n <= 9999:
                num_blocks.append((cy, cx, n))

    results = {}
    for room_num, room_name in rooms.items():
        # 방 이름과 가장 유사한 텍스트 블록 찾기 (유사도 0.45 이상)
        best_ratio = 0.45
        best_pos = None
        for cy, cx, text in blocks:
            ratio = SequenceMatcher(None, room_name, text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = (cy, cx)

        if best_pos is None:
            continue

        ref_y, ref_x = best_pos
        # 같은 행(y ±40px)에서 오른쪽에 있는 숫자 중 가장 가까운 것
        candidates = [
            (abs(cy - ref_y), cx, n)
            for cy, cx, n in num_blocks
            if abs(cy - ref_y) < 40 and cx >= ref_x
        ]
        if candidates:
            candidates.sort()
            results[room_num] = candidates[0][2]

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def _parse_easyocr_text(raw: list) -> list:
    """rooms 없을 때 — 추출된 텍스트로 기존 패턴 파싱."""
    lines = [text for _, text, _ in raw]
    return _parse_rows(lines)


def _extract_tesseract(image: Image.Image) -> list:
    """EasyOCR 실패 시 Tesseract 폴백."""
    import pytesseract
    from image_processor import preprocess_for_ocr
    image = preprocess_for_ocr(image)
    best = {}
    for cfg in ['--oem 3 --psm 11 -l kor+eng', '--oem 3 --psm 6 -l kor+eng']:
        text = pytesseract.image_to_string(image, config=cfg)
        for r in _parse_rows(text.strip().splitlines()):
            if r['room_num'] not in best:
                best[r['room_num']] = r['members']
    return [{'room_num': k, 'members': v} for k, v in sorted(best.items())]


def _parse_rows(rows: list) -> list:
    """텍스트 줄 목록에서 채팅방 번호 + 인원 수 추출."""
    results = {}
    for line in rows:
        room_match = re.search(r'채팅방\s*(\d{1,3})', line)
        if not room_match:
            continue
        room_num = int(room_match.group(1))
        if room_num in results:
            continue
        after = line[room_match.end():]
        after = re.sub(r'^번', '', after)
        after = re.sub(r'\([^)]*\)', ' ', after)
        # 콤마 포함 숫자(1,817)와 일반 숫자 모두 처리
        nums = re.findall(r'\b(\d{1,3}(?:,\d{3})*|\d{1,4})\b', after)
        valid = [int(n.replace(',', '')) for n in nums if 1 <= int(n.replace(',', '')) <= 9999]
        if valid:
            results[room_num] = valid[0]
    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def parse_from_text(raw_text: str) -> list:
    lines = raw_text.strip().splitlines()
    return _parse_rows(lines)