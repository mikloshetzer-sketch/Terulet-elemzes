from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


def _load_image(path: str) -> Image.Image:
    image_path = Path(path)

    if not image_path.exists():
        raise FileNotFoundError(f"Hiányzik a kép: {image_path}")

    return Image.open(image_path).convert("RGB")


def _resize_to_same_height(
    left: Image.Image, right: Image.Image
) -> Tuple[Image.Image, Image.Image]:
    target_height = min(left.height, right.height)

    def resize(image: Image.Image) -> Image.Image:
        if image.height == target_height:
            return image
        new_width = int(image.width * (target_height / image.height))
        return image.resize((new_width, target_height))

    return resize(left), resize(right)


def create_side_by_side_comparison(
    before_image_path: str,
    after_image_path: str,
    output_folder: Path,
    before_label: str = "BEFORE",
    after_label: str = "AFTER",
) -> Path:
    before_image = _load_image(before_image_path)
    after_image = _load_image(after_image_path)

    before_image, after_image = _resize_to_same_height(before_image, after_image)

    padding = 20
    header_height = 50
    width = before_image.width + after_image.width + padding * 3
    height = max(before_image.height, after_image.height) + padding * 2 + header_height

    canvas = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    before_x = padding
    after_x = before_image.width + padding * 2
    image_y = padding + header_height

    canvas.paste(before_image, (before_x, image_y))
    canvas.paste(after_image, (after_x, image_y))

    draw.text((before_x, padding), before_label, fill="black", font=font)
    draw.text((after_x, padding), after_label, fill="black", font=font)

    divider_x = before_image.width + padding + (padding // 2)
    draw.line(
        [(divider_x, padding), (divider_x, height - padding)],
        fill="black",
        width=2,
    )

    output_file = output_folder / "comparison_side_by_side.jpg"
    canvas.save(output_file, quality=95)

    return output_file


def print_comparison_summary(output_file: Path) -> None:
    print("\n=== Összehasonlító kép elkészült ===")
    print(f"Kimeneti fájl: {output_file.resolve()}")
    print("===================================\n")
