from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    img = image.convert('L')  # 그레이스케일

    # 다크 모드 감지: 평균 밝기가 128 미만이면 배경이 어두운 것 → 반전
    pixels = list(img.getdata())
    avg_brightness = sum(pixels) / len(pixels)
    if avg_brightness < 128:
        img = ImageOps.invert(img)

    img = img.convert('RGB')
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    return img
