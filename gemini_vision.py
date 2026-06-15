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
    short = [m.split("/")[-1] for m in model_names]
    short_set = set(short)

    # 1순위: 정확한 이름 매칭
    for preferred in _PREFERRED:
        if preferred in short_set:
            return preferred

    # 2순위: prefix 매칭 (버전 suffix 대응, 예: gemini-2.0-flash-001)
    for preferred in _PREFERRED:
        for name in short:
            if name.startswith(preferred):
                return name

    # 3순위: flash 또는 pro 계열 아무거나
    for name in short:
        if ("flash" in name or "pro" in name) and "vision" not in name:
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

    # 2단계: 이미지 인코딩 (최대 1600px로 리사이즈 후 JPEG 압축)
    img_rgb = image.convert("RGB")
    max_side = 1600
    w, h = img_rgb.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        _resample = getattr(Image, "Resampling", Image).LANCZOS
        img_rgb = img_rgb.resize((int(w * ratio), int(h * ratio)), _resample)
    buf = io.BytesIO()
    img_rgb.save(buf, format="JPEG", quality=88, optimize=True)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    mime_type = "image/jpeg"

    room_list = "\n".join(
        f"- room_num={num}, name=\"{name}\"" for num, name in rooms.items()
    )
    prompt = (
        "이 이미지는 카카오톡 오픈채팅방 목록 스크린샷입니다.\n\n"
        "【중요 구분】\n"
        "- 왼쪽 원형 배지 안의 숫자(예: 32, 35)는 채팅방 식별 번호입니다. 인원 수가 아닙니다.\n"
        "- 인원 수는 채팅방 이름 텍스트 끝 부분에 공백으로 구분되어 나타나는 숫자입니다.\n"
        "  예시: '황금후수 돈버는 채팅방35(사주3) 545' → 인원=545, '황금후수 돈버는 채팅방32 1252' → 인원=1252\n\n"
        "아래 등록된 채팅방들의 인원 수를 이미지에서 찾아 JSON으로 반환해주세요.\n\n"
        f"등록된 채팅방 (room_num=채팅방 번호):\n{room_list}\n\n"
        "규칙:\n"
        "1. 채팅방 이름에 포함된 숫자(채팅방N)로 room_num을 매칭하세요\n"
        "2. 인원 수는 채팅방 이름 바로 뒤에 오는 숫자입니다 (보통 50~9999 범위)\n"
        "3. 왼쪽 원형 배지 숫자는 절대 인원 수로 사용하지 마세요\n"
        "4. 이미지에서 명확히 보이지 않는 방은 결과에서 완전히 제외하세요\n"
        "5. 쉼표 제거 후 정수로 반환 (1,234 → 1234)\n\n"
        "JSON 형식으로만 응답:\n"
        "{\"results\": [{\"room_num\": 35, \"members\": 545}, {\"room_num\": 34, \"members\": 152}]}"
    )

    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime_type, "data": img_b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }

    url = f"{_BASE}/v1beta/models/{model}:generateContent?key={api_key}"
    resp = requests.post(url, json=body, timeout=60)

    if resp.status_code != 200:
        try:
            err = resp.json().get("error", {}).get("message", resp.text[:300])
        except Exception:
            err = resp.text[:300]
        code = resp.status_code
        hint = ""
        if code == 429:
            hint = " (할당량 초과 — 잠시 후 다시 시도하세요)"
        elif code == 400:
            hint = " (잘못된 요청 — 이미지 형식 또는 API 키 확인)"
        elif code == 403:
            hint = " (권한 오류 — Generative Language API 활성화 여부 확인)"
        raise RuntimeError(f"Gemini 호출 실패 [{code}]{hint}\n모델={model}\n{err}")

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
            # m == rn 이면 배지 번호를 인원으로 오인식한 것 → 제외
            if rn in rooms and 1 <= m <= 99999 and m != rn:
                valid.append({"room_num": rn, "members": m})
        return valid
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
