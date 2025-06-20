from PIL import Image, ImageDraw, ImageFont
import os

def generate_flashcard_image(russian_word: str, output_path: str = None) -> str:
    width, height = 600, 400
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    if output_path is None:
        output_path = os.path.join(os.getcwd(), "flashcard.png")

    # Try DejaVuSans, then Arial (Windows), then default font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size=48)
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", size=48)
        except IOError:
            font = ImageFont.load_default()

    text = russian_word
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)

    draw.text(position, text, fill="black", font=font)

    img.save(output_path)
    return output_path
