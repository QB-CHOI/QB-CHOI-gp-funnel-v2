"""
Gemini Vision OCR — 카카오톡 오픈채팅방 스크린샷에서 인원 추출
모델: gemini-1.5-flash (무료 1500회/일)
"""
import base64
import io
import json
import re
from PIL import Image


def extract_members(image: Image.Image, api_key: str, rooms: dict) -> list:
    """
    Gemini Vision으로 카카오톡 스크린샷에서 채팅방 인원 추출.
    rooms: {room_num: room_name}
    반환: [{'room_num': int, 'members': int}, ...]
    """
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # 이미지 → base64
    buf = io.BytesIO()
    image.convert('RGB').save(buf, format='PNG')
    img_data = buf.getvalue()

    # 등록된 방 목록 텍스트
    room_list = "\n".join(f"- room_num={num}, name=\"{name}\"" for num, name in rooms.items())

    prompt = f"""이 이미지는 카카오톡 오픈채팅방 목록 스크린샷입니다.
아래 등록된 채팅방들의 현재 인원 수(숫자)를 찾아서 JSON으로 반환해주세요.

등록된 채팅방:
{room_list}

규칙:
- 각 채팅방 이름 옆에 표시된 인원 수(예: 1,234 또는 1234)를 읽어주세요
- 인원이 보이지 않는 방은 결과에서 제외하세요
- 숫자만 반환하세요 (쉼표 없이 정수)

반드시 아래 JSON 형식으로만 응답하세요:
{{"results": [{{"room_num": 1, "members": 1234}}, {{"room_num": 2, "members": 567}}]}}"""

    response = model.generate_content([
        {'mime_type': 'image/png', 'data': base64.b64encode(img_data).decode()},
        prompt,
    ])

    return _parse_response(response.text, rooms)


def _parse_response(text: str, rooms: dict) -> list:
    """Gemini 응답 텍스트에서 JSON 파싱."""
    # JSON 블록 추출 (마크다운 코드블록 포함)
    text = re.sub(r'```(?:json)?', '', text).strip()

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return []

    try:
        data = json.loads(match.group())
        results = data.get('results', [])
        valid = []
        for r in results:
            rn = int(r.get('room_num', 0))
            m = int(r.get('members', 0))
            if rn in rooms and 1 <= m <= 99999:
                valid.append({'room_num': rn, 'members': m})
        return valid
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
