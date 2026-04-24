import cv2
import numpy as np
from PIL import Image


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """
    OCR 정확도를 높이기 위한 이미지 전처리.
    1. 2배 확대 (작은 글씨 인식률 향상)
    2. 선명화 필터 적용
    3. 대비 강화 (CLAHE)
    """
    img = np.array(image.convert('RGB'))
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # 2배 확대 — 작은 글씨 인식률 크게 향상
    scaled = cv2.resize(img_bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LANCZOS4)

    # 선명화 (언샤프 마스크)
    blurred = cv2.GaussianBlur(scaled, (0, 0), 3)
    sharpened = cv2.addWeighted(scaled, 1.5, blurred, -0.5, 0)

    # 대비 강화 (채널별 CLAHE)
    lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    enhanced = cv2.merge([l_ch, a_ch, b_ch])
    result_bgr = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(result_rgb)


def crop_chat_list_area(image: Image.Image) -> Image.Image:
    """
    카카오톡 채팅방 목록에서 채팅방 이름·인원 숫자 영역만 잘라냄.
    좌측 아이콘 영역(약 15%)과 우측 날짜 영역(약 15%)을 제거.
    """
    w, h = image.size
    left = int(w * 0.15)
    right = int(w * 0.85)
    return image.crop((left, 0, right, h))
