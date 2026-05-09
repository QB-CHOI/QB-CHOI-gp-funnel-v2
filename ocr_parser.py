import re
import pytesseract
from PIL import Image


def extract_from_image(image: Image.Image) -> list:
    from image_processor import preprocess_for_ocr
    image = preprocess_for_ocr(image)
    text = pytesseract.image_to_string(image, config='--oem 3 --psm 6 -l kor+eng')
    lines = text.strip().splitlines()
    return _parse_rows(lines)


def _parse_rows(rows: list) -> list:
    results = {}
    for line in rows:
        room_match = re.search(r'채팅방\s*(\d+)', line)
        if not room_match:
            continue
        room_num = int(room_match.group(1))
        if room_num in results:
            continue
        after = line[room_match.end():]
        after = re.sub(r'^번', '', after)
        after = re.sub(r'\([^)]*\)', ' ', after)
        after = after.strip()
        nums = re.findall(r'\b(\d{1,4})\b', after)
        valid = [int(n) for n in nums if 1 <= int(n) <= 9999]
        if valid:
            results[room_num] = valid[0]
    return [{'room_num': k, 'members': v} for k, v in sorted(results.items())]


def parse_from_text(raw_text: str) -> list:
    lines = raw_text.strip().splitlines()
    return _parse_rows(lines)
