"""
Gemini Vision OCR — REST API 직접 호출
1단계: 키 유효성 + 사용 가능한 모델 목록 확인
2단계: 비전 지원 모델로 인원 추출
"""
import base64
import io
import json
import re
import requests
from PIL import Image

_BASE = "https://generativelanguage.googleapis.com"

# 선호 순서 (앞에 있을수록 먼저 시도)
_PREFERRED = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
]


def _list_models(api_key: str) -> list:
    """사용 가능한 모델 목록 반환. 키 오류 시 예외 발생."""
    url = f"{_BASE}/v1beta/models?key={api_key}"
    resp = requests.get(url, timeout=15)

    if resp.status_code == 400:
        body = resp.json()
        msg = body.get("error", {}).get("message", "알 수 없는 오류")
        raise ValueError(f"API 키 오류: {msg}")
    if resp.status_code == 403:
        raise ValueError("API 키 권한 오류 (403). Generative Language API가 활성화되어 있는지 확인하세요.")

    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]


def _pick_vision_model(model_names: list) -> str | None:
    """generateContent + 비전 지원 모델 선택."""
    # "models/gemini-xxx" → "gemini-xxx"
    short = {m.split("/")[-1] for m in model_names}

    for preferred in _PREFERRED:
        if preferred in short:
            return preferred
    # 선호 목록에 없으면 flash 계열 아무거나
    for name in short:
        if "flash" in name or "pro" in name:
            return name
    return None


def extract_members(image: Image.Image, api_key: str, rooms: dict) -> list:
    """Gemini Vision으로 카카오톡 스크린샷에서 채팅방 인원 추출."""

    # 1단계: 키 검증 + 모델 자동 선택
    try:
        available = _list_models(api_key)
    except ValueError as e:
        raise RuntimeError(str(e))

    model = _pick_vision_model(available)
    if model is None:
        avail_str = ", ".join(available[:10])
        raise RuntimeError(
            f"비전 지원 Gemini 모델을 찾을 수 없습니다.\n"
            f"사용 가능한 모델: {avail_str}"
        )

    # 2단계: 이미지 인코딩
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
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
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/png", "data": img_b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }

    url = f"{_BASE}/v1beta/models/{model}:generateContent?key={api_key}"
    resp = requests.post(url, json=body, timeout=30)

    if resp.status_code != 200:
        err = resp.json().get("error", {}).get("message", resp.text[:200])
        raise RuntimeError(f"Gemini 호출 실패 [{resp.status_code}] 모델={model}: {err}")

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_response(text, rooms)


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
            if rn in rooms and 1 <= m <= 99999:
                valid.append({"room_num": rn, "members": m})
        return valid
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
