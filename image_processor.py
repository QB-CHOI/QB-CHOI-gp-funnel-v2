from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def preprocess_for_ocr(image: Image.Image, scale: int = 2) -> Image.Image:
    img = image.convert('L')

    # 다크 모드: 평균 밝기 < 128 이면 반전
    pixels = list(img.getdata())
    avg_brightness = sum(pixels) / len(pixels)
    if avg_brightness < 128:
        img = ImageOps.invert(img)

    # 히스토그램 스트레치 (자동 대비)
    img = ImageOps.autocontrast(img, cutoff=2)

    img = img.convert('RGB')
    w, h = img.size
    img = img.resize((w * scale, h * scale), Image.LANCZOS)
    img = img.filter(ImageFilter.MedianFilter(size=3))  # 노이즈 제거
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    return img


def preprocess_badge_region(image: Image.Image) -> Image.Image:
    """원형 배지 안 숫자는 작으므로 3× 업스케일로 인식률을 높임."""
    return preprocess_for_ocr(image, scale=3)
