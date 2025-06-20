import os
import random
from io import BytesIO
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps
from aiogram.types import BufferedInputFile
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурационные параметры
class FlashcardConfig:
    FONT_PATHS = {
        'main': 'fonts/arial.ttf',
        'fallback': None
    }
    IMAGE_SIZE = (800, 600)
    BORDER = {
        'size': 10,
        'color': (0, 0, 0)
    }
    TEXT_COLOR = (10, 20, 40)  # Dark Navy Blue
    FONT_SIZES = {
        'title': 42,
        'question': 60,
        'answer': 48
    }
    MAX_TEXT_LENGTH = 30
    RANDOM_COLOR_PALETTE = [
        (249, 110, 42),   # F96E2A
        (72, 92, 139),    # 485C8B
        (255, 231, 183),  # FFE7B7
        (251, 248, 239),  # FBF8EF
        (246, 152, 62),   # F6983E
        (201, 230, 240),  # C9E6F0
        (253, 213, 141),  # FDD58D
        (120, 179, 206)   # 78B3CE
    ]

class FlashcardGenerator:
    def __init__(self):
        self._load_fonts()

    def _load_fonts(self):
        self.fonts = {}
        try:
            for key in FlashcardConfig.FONT_SIZES:
                self.fonts[key] = ImageFont.truetype(
                    FlashcardConfig.FONT_PATHS['main'], 
                    FlashcardConfig.FONT_SIZES[key]
                )
        except Exception as e:
            logger.warning(f"Font loading failed: {e}")
            fallback_font = ImageFont.load_default()
            self.fonts = {k: fallback_font for k in FlashcardConfig.FONT_SIZES}

    async def generate_flashcard(self, text: str, is_question: bool = True) -> BufferedInputFile:
        try:
            return await self._generate_with_random_color(text, is_question)
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return await self._generate_error_card()

    async def _generate_with_random_color(self, text: str, is_question: bool) -> BufferedInputFile:
        try:
            color = random.choice(FlashcardConfig.RANDOM_COLOR_PALETTE)
            img = Image.new('RGB', FlashcardConfig.IMAGE_SIZE, color)
            draw = ImageDraw.Draw(img)
            self._draw_text(draw, text, is_question)
            img = self._add_border(img)
            return self._image_to_telegram_file(img)
        except Exception as e:
            logger.error(f"Color card generation error: {e}")
            return await self._generate_error_card()

    def _draw_text(self, draw: ImageDraw.Draw, text: str, is_question: bool):
        font_key = 'question' if is_question else 'answer'
        lines = self._split_text(text)
        for i, line in enumerate(lines):
            y_pos = FlashcardConfig.IMAGE_SIZE[1] // 2 + i * (FlashcardConfig.FONT_SIZES[font_key] + 10)
            draw.text(
                (FlashcardConfig.IMAGE_SIZE[0] // 2, y_pos),
                line,
                font=self.fonts[font_key],
                fill=FlashcardConfig.TEXT_COLOR,
                anchor="mm"
            )

    def _split_text(self, text: str) -> list:
        if len(text) <= FlashcardConfig.MAX_TEXT_LENGTH:
            return [text]
        words, lines, current = text.split(), [], ""
        for word in words:
            if len(current + ' ' + word) <= FlashcardConfig.MAX_TEXT_LENGTH:
                current += f" {word}" if current else word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _add_border(self, img: Image.Image) -> Image.Image:
        return ImageOps.expand(img, border=FlashcardConfig.BORDER['size'], fill=FlashcardConfig.BORDER['color'])

    def _image_to_telegram_file(self, img: Image.Image) -> BufferedInputFile:
        with BytesIO() as buffer:
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return BufferedInputFile(buffer.getvalue(), filename="flashcard.png")

    async def _generate_error_card(self) -> BufferedInputFile:
        img = Image.new('RGB', FlashcardConfig.IMAGE_SIZE, (255, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text(
            (FlashcardConfig.IMAGE_SIZE[0] // 2, FlashcardConfig.IMAGE_SIZE[1] // 2),
            "Ошибка генерации карточки",
            font=self.fonts['title'],
            fill=(255, 255, 255),
            anchor="mm"
        )
        return self._image_to_telegram_file(img)

flashcard_generator = FlashcardGenerator()

async def generate_flashcard_image(*args, **kwargs):
    return await flashcard_generator.generate_flashcard(*args, **kwargs)
