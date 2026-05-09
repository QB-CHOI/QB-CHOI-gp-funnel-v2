import re
import pytesseract
from PIL import Image


def extract_from_image(image: Image.Image) -> list:
    from image_processor import preprocess_for_ocr
    image = preprocess_for_ocr(image)

    # PSM 11: 배치 무관 sparse text — 채팅 목록처럼 구조가 복잡할 때 유리
    configs = [
        '--oem 3 --psm 11 -l kor+eng',
        '--oem 3 --psm 6 -l kor+eng',
        '--oem 3 --psm 4 -l kor+eng',
    ]

    best = {}
    for cfg in configs:
        text = pytesseract.image_to_string(image, config=cfg)
        lines = text.strip().splitlines()
        result = _parse_rows(lines)
        for r in result:
            if r['room_num'] not in best:
                best[r['room_num']] = r['members']

    return [{'room_num': k, 'members': v} for k, v in sorted(best.items())]


def _parse_rows(rows: list) -> list:
    results = {}

    for line in rows:
        # '채팅방' 뒤 숫자 추출 (공백 무관)
        room_match = re.search(r'채팅방\s*(\d{1,3})', line)
        if not room_match:
            continue

        room_num = int(room_match.group(1))
        if room_num in results:
            continue

        after = line[room_match.end():]
        after = re.sub(r'^번', '', after)          # '37번' 처리
        after = re.sub(r'\([^)]*\)', ' ', after)   # '(사주2)' 제거
        after = after.strip()

        # 1~9999 범위의 숫자 중 첫 번째 유효값 (날짜·년도 제외)
        nums = re.findall(r'\b(\d{1,4})\b', after)
        valid = [int(n) for n in nums if 1 <= int(n) <= 9999]

        if valid:
            results[room_num] = valid[0]

    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def parse_from_text(raw_text: str) -> list:
    lines = raw_text.strip().splitlines()
    return _parse_rows(lines)
