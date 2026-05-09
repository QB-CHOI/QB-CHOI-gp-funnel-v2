from PIL import Image, ImageEnhance, ImageFilter


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    img = image.convert('RGB')
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    return img


def crop_chat_list_area(image: Image.Image) -> Image.Image:
    w, h = image.size
    left = int(w * 0.15)
    right = int(w * 0.85)
    return image.crop((left, 0, right, h))
