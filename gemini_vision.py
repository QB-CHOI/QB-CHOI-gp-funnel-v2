"""
Gemini Vision OCR — 모델 목록 조회 없이 직접 호출, 실패 시 다음 모델 시도
"""
import base64
import io
import json
import re
import requests
from PIL import Image

_BASE = "https://generativelanguage.googleapis.com"

_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def _encode_image(image: Image.Image) -> tuple[str, str]:
    """이미지를 최대 1600px JPEG로 압축해 (base64, mime_type) 반환."""
    img = image.convert("RGB")
    w, h = img.size
    if max(w, h) > 1600:
        ratio = 1600 / max(w, h)
        resample = getattr(getattr(Image, "Resampling", None), "LANCZOS", None) or Image.LANCZOS
        img = img.resize((int(w * ratio), int(h * ratio)), resample)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def _call_model(model: str, img_b64: str, mime_type: str,
                prompt: str, api_key: str) -> dict:
    """단일 모델 호출. 응답 dict 반환, 실패 시 예외."""
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime_type, "data": img_b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }
    url = f"{_BASE}/v1beta/models/{model}:generateContent?key={api_key}"
    resp = requests.post(url, json=body, timeout=45)
    if resp.status_code == 200:
        return resp.json()
    try:
        err = resp.json().get("error", {}).get("message", resp.text[:200])
    except Exception:
        err = resp.text[:200]
    raise RuntimeError(f"[{resp.status_code}] {model}: {err}")


def extract_members(image: Image.Image, api_key: str, rooms: dict) -> list:
    """Gemini Vision으로 채팅방 인원 추출. 모델 순서대로 시도."""
    img_b64, mime_type = _encode_image(image)

    room_list = "\n".join(
        f"- room_num={num}, name=\"{name}\"" for num, name in rooms.items()
    )
    prompt = (
        "이 이미지는 카카오톡 오픈채팅방 목록 스크린샷입니다.\n\n"
        "【중요 구분】\n"
        "- 왼쪽 원형 배지 안의 숫자(예: 32, 35)는 채팅방 식별 번호입니다. 인원 수가 아닙니다.\n"
        "- 인원 수는 채팅방 이름 텍스트 끝 부분에 공백으로 구분되어 나타나는 숫자입니다.\n"
        "  예시: '황금후추 채팅방35(사주3) 545' → 인원=545\n\n"
        f"등록된 채팅방:\n{room_list}\n\n"
        "규칙:\n"
        "1. 채팅방 이름에 포함된 숫자(채팅방N)로 room_num 매칭\n"
        "2. 인원 수는 채팅방 이름 바로 뒤 숫자 (50~9999 범위)\n"
        "3. 왼쪽 원형 배지 숫자는 절대 인원 수로 사용하지 말 것\n"
        "4. 명확히 보이지 않는 방은 제외\n"
        "5. 쉼표 제거 후 정수 반환 (1,234 → 1234)\n\n"
        "JSON으로만 응답:\n"
        "{\"results\": [{\"room_num\": 35, \"members\": 545}]}"
    )

    errors = []
    for model in _MODELS:
        try:
            data = _call_model(model, img_b64, mime_type, prompt, api_key)
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            result = _parse_response(text, rooms)
            if result:
                return result
        except Exception as e:
            errors.append(str(e))
            continue

    raise RuntimeError("모든 Gemini 모델 시도 실패:\n" + "\n".join(errors))


def _parse_response(text: str, rooms: dict) -> list:
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        valid = []
        for r in data.get("results", []):
            rn = int(r.get("room_num", 0))
            m  = int(r.get("members", 0))
            if rn in rooms and 1 <= m <= 99999 and m != rn:
                valid.append({"room_num": rn, "members": m})
        return valid
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
