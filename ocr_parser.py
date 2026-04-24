import re
import numpy as np


def _get_reader():
    import easyocr
    return easyocr.Reader(['ko', 'en'], verbose=False)


def extract_from_image(image) -> list:
    """
    PIL Image를 받아 채팅방 번호 + 인원 수 목록을 반환.
    Returns: [{'room_num': int, 'members': int}, ...]
    """
    from image_processor import preprocess_for_ocr, crop_chat_list_area
    image = crop_chat_list_area(image)
    image = preprocess_for_ocr(image)

    reader = _get_reader()
    img_array = np.array(image.convert('RGB'))
    ocr_results = reader.readtext(img_array)

    rows = _group_by_row(ocr_results, y_threshold=25)
    return _parse_rows(rows)


def _group_by_row(ocr_results: list, y_threshold: int = 25) -> list:
    """Y 좌표 기준으로 텍스트 블록을 행으로 묶어 반환."""
    if not ocr_results:
        return []

    # Y 중심값 기준 정렬
    tagged = []
    for bbox, text, conf in ocr_results:
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_left = bbox[0][0]
        tagged.append((y_center, x_left, text))

    tagged.sort(key=lambda t: t[0])

    rows = []
    current_y = None
    current_row = []

    for y_center, x_left, text in tagged:
        if current_y is None or abs(y_center - current_y) <= y_threshold:
            current_row.append((x_left, text))
            current_y = y_center if current_y is None else (current_y + y_center) / 2
        else:
            if current_row:
                line = ' '.join(t for _, t in sorted(current_row))
                rows.append(line)
            current_row = [(x_left, text)]
            current_y = y_center

    if current_row:
        rows.append(' '.join(t for _, t in sorted(current_row)))

    return rows


def _parse_rows(rows: list) -> list:
    """
    각 행에서 '채팅방XX ... 숫자' 패턴을 찾아 room_num, members 추출.
    같은 방 번호가 여러 행에 나오면 첫 번째만 사용.
    """
    results = {}

    for line in rows:
        # 채팅방 번호 추출
        room_match = re.search(r'채팅방\s*(\d+)', line)
        if not room_match:
            continue

        room_num = int(room_match.group(1))
        if room_num in results:
            continue

        # 방 번호 이후 텍스트에서 인원 수 추출
        after = line[room_match.end():]
        after = re.sub(r'^번', '', after)           # '37번' 처리
        after = re.sub(r'\([^)]*\)', ' ', after)   # '(사주2)' 제거
        after = after.strip()

        # 첫 번째 유효 숫자 (1~9999) 추출 — 연도·월 등 큰 수 제외
        nums = re.findall(r'\b(\d{1,4})\b', after)
        valid = [int(n) for n in nums if 1 <= int(n) <= 9999]

        if valid:
            results[room_num] = valid[0]

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def parse_from_text(raw_text: str) -> list:
    """
    OCR 없이 텍스트를 직접 붙여넣기해서 파싱할 때 사용.
    카카오톡 채팅방 목록을 텍스트로 복사한 경우.
    """
    lines = raw_text.strip().splitlines()
    return _parse_rows(lines)
