import io
import base64
import json
import anthropic
from PIL import Image


def extract_members(image: Image.Image, api_key: str, rooms: dict) -> list:
    """Claude Vision으로 채팅방 인원 추출.
    rooms: {room_num: room_name}
    반환: [{'room_num': int, 'members': int}, ...]
    """
    client = anthropic.Anthropic(api_key=api_key)

    buf = io.BytesIO()
    image.save(buf, format='PNG')
    img_b64 = base64.standard_b64encode(buf.getvalue()).decode('utf-8')

    room_list = "\n".join([f"{num}: {name}" for num, name in sorted(rooms.items())])

    prompt = f"""이 이미지는 카카오톡 오픈채팅방 목록 화면입니다.

아래 등록된 채팅방의 현재 인원 수를 이미지에서 찾아 추출해주세요.
- 쉼표 포함 숫자(예: 1,817)도 정확히 읽어주세요
- 채팅방 이름이 화면과 완전히 일치하지 않아도 가장 유사한 방과 매칭하세요
- 이미지에 보이지 않는 채팅방은 제외하세요

등록된 채팅방 (번호: 이름):
{room_list}

JSON 형식으로만 답변하세요 (다른 설명 없이):
{{"results": [{{"room_num": 37, "members": 1817}}, ...]}}"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    raw = msg.content[0].text
    try:
        start = raw.find('{')
        end = raw.rfind('}') + 1
        data = json.loads(raw[start:end])
        results = []
        for r in data.get('results', []):
            rn = r.get('room_num')
            mb = r.get('members')
            if rn is not None and mb is not None:
                results.append({'room_num': int(rn), 'members': int(str(mb).replace(',', ''))})
        return results
    except Exception:
        return []
