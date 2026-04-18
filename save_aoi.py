import json
from pathlib import Path
from typing import Dict


def save_aoi_to_json(bbox: Dict, output_folder: Path) -> Path:
    """
    Elmenti az AOI bounding boxot JSON fájlba.
    """
    output_file = output_folder / "aoi.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(bbox, f, indent=4, ensure_ascii=False)

    return output_file


def print_save_confirmation(file_path: Path) -> None:
    print(f"AOI elmentve ide: {file_path.resolve()}")
