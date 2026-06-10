"""
Gemini Vision OCR — 카카오톡 오픈채팅방 스크린샷에서 인원 추출
사용 가능한 모델을 순서대로 시도하여 404 오류 방지
"""
import base64
import io
import json
import re
from PIL import Image

# 우선순위 순서로 시도할 모델 목록
_CANDIDATE_MODELS = [
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash-001',
    'gemini-1.0-pro-vision',
    'gemini-pro-vision',
]


def extract_members(image: Image.Image, api_key: str, rooms: dict) -> list:
    """
    Gemini Vision으로 카카오톡 스크린샷에서 채팅방 인원 추출.
    모델을 순서대로 시도해 404 오류 시 다음 모델로 자동 전환.
    rooms: {room_num: room_name}
    반환: [{'room_num': int, 'members': int}, ...]
    """
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    # 이미지 → bytes
    buf = io.BytesIO()
    image.convert('RGB').save(buf, format='PNG')
    img_bytes = buf.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()

    room_list = "\n".join(f"- room_num={num}, name=\"{name}\"" for num, name in rooms.items())
    prompt = f"""이 이미지는 카카오톡 오픈채팅방 목록 스크린샷입니다.
아래 등록된 채팅방들의 현재 인원 수(숫자)를 찾아서 JSON으로 반환해주세요.

등록된 채팅방:
{room_list}

규칙:
- 각 채팅방 이름 옆에 표시된 인원 수(예: 1,234 또는 1234)를 읽어주세요
- 인원이 보이지 않는 방은 결과에서 제외하세요
- 숫자만 반환 (쉼표 없이 정수)

반드시 아래 JSON 형식으로만 응답:
{{"results": [{{"room_num": 1, "members": 1234}}, {{"room_num": 2, "members": 567}}]}}"""

    last_error = None
    for model_name in _CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([
                {'mime_type': 'image/png', 'data': img_b64},
                prompt,
            ])
            return _parse_response(response.text, rooms)
        except Exception as e:
            err_str = str(e)
            # 404(모델 없음) / 400(지원 안 함) 이면 다음 모델 시도
            if any(code in err_str for code in ['404', '400', 'not found', 'not supported', 'INVALID_ARGUMENT']):
                last_error = e
                continue
            # 그 외(401 인증 실패, 네트워크 등)는 즉시 올려보냄
            raise

    raise RuntimeError(
        f"사용 가능한 Gemini 모델을 찾을 수 없습니다. "
        f"마지막 오류: {last_error}\n"
        f"시도한 모델: {', '.join(_CANDIDATE_MODELS)}"
    )


def _parse_response(text: str, rooms: dict) -> list:
    """Gemini 응답 텍스트에서 JSON 파싱."""
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
            m  = int(r.get('members', 0))
            if rn in rooms and 1 <= m <= 99999:
                valid.append({'room_num': rn, 'members': m})
        return valid
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
