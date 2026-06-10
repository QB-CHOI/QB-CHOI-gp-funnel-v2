"""
Gemini Vision OCR — REST API 직접 호출 방식 (SDK 미사용)
google-generativeai 패키지 버전과 무관하게 동작
"""
import base64
import io
import json
import re
import requests
from PIL import Image

_BASE = "https://generativelanguage.googleapis.com"

# (api_version, model_name) 순서대로 시도
_ENDPOINTS = [
    ("v1",     "gemini-1.5-flash"),
    ("v1",     "gemini-2.0-flash"),
    ("v1",     "gemini-1.5-flash-latest"),
    ("v1",     "gemini-1.5-pro"),
    ("v1beta", "gemini-1.5-flash"),
    ("v1beta", "gemini-2.0-flash-exp"),
    ("v1beta", "gemini-1.5-flash-latest"),
    ("v1beta", "gemini-pro-vision"),
]


def extract_members(image: Image.Image, api_key: str, rooms: dict) -> list:
    """
    Gemini REST API로 카카오톡 스크린샷에서 채팅방 인원 추출.
    rooms: {room_num: room_name}
    반환: [{'room_num': int, 'members': int}, ...]
    """
    buf = io.BytesIO()
    image.convert('RGB').save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    room_list = "\n".join(
        f"- room_num={num}, name=\"{name}\"" for num, name in rooms.items()
    )
    prompt = (
        "이 이미지는 카카오톡 오픈채팅방 목록 스크린샷입니다.\n"
        "아래 등록된 채팅방들의 현재 인원 수를 찾아서 JSON으로 반환해주세요.\n\n"
        f"등록된 채팅방:\n{room_list}\n\n"
        "규칙:\n"
        "- 각 채팅방 이름 옆에 표시된 인원 수(예: 1,234 또는 1234)를 읽어주세요\n"
        "- 인원이 보이지 않는 방은 결과에서 제외하세요\n"
        "- 숫자만 반환 (쉼표 없이 정수)\n\n"
        "반드시 아래 JSON 형식으로만 응답:\n"
        "{\"results\": [{\"room_num\": 1, \"members\": 1234}, {\"room_num\": 2, \"members\": 567}]}"
    )

    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }

    last_error = None
    for api_ver, model_name in _ENDPOINTS:
        url = f"{_BASE}/{api_ver}/models/{model_name}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, json=body, timeout=30)
            if resp.status_code in (400, 404):
                last_error = f"{model_name} [{resp.status_code}]"
                continue
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_response(text, rooms)
        except (requests.RequestException, KeyError, IndexError) as e:
            last_error = f"{model_name}: {e}"
            continue

    raise RuntimeError(
        f"Gemini API 호출 실패 — 시도한 모든 모델/버전에서 응답 없음.\n"
        f"마지막 오류: {last_error}\n"
        "Google AI Studio(aistudio.google.com)에서 API 키를 다시 확인해주세요."
    )


def _parse_response(text: str, rooms: dict) -> list:
    text = re.sub(r'```(?:json)?', '', text).strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        valid = []
        for r in data.get('results', []):
            rn = int(r.get('room_num', 0))
            m  = int(r.get('members', 0))
            if rn in rooms and 1 <= m <= 99999:
                valid.append({'room_num': rn, 'members': m})
        return valid
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
