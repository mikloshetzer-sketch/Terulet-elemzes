from pathlib import Path
import sys
import yaml

from aoi import build_bounding_box, print_bounding_box_summary
from save_aoi import save_aoi_to_json, print_save_confirmation
from data_fetch import (
    load_aoi,
    build_data_request,
    save_data_request,
    print_data_request_summary,
    fetch_true_color_preview,
    print_download_summary,
)


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Hiányzik a konfigurációs fájl: {config_path}")

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("A config.yaml tartalma nem értelmezhető szótárként.")

    return config


def validate_config(config: dict) -> None:
    required_top_level = [
        "project_name",
        "location",
        "area_of_interest",
        "time_range",
        "data_source",
        "analysis",
        "output",
    ]

    for key in required_top_level:
        if key not in config:
            raise ValueError(f"Hiányzó felső szintű mező a configban: {key}")

    required_location = ["name", "latitude", "longitude"]
    for key in required_location:
        if key not in config["location"]:
            raise ValueError(f"Hiányzó location mező: {key}")

    required_time_range = ["start_date", "end_date"]
    for key in required_time_range:
        if key not in config["time_range"]:
            raise ValueError(f"Hiányzó time_range mező: {key}")

    required_data_source = ["satellite", "cloud_cover_max"]
    for key in required_data_source:
        if key not in config["data_source"]:
            raise ValueError(f"Hiányzó data_source mező: {key}")

    required_analysis = ["type", "output_resolution_m"]
    for key in required_analysis:
        if key not in config["analysis"]:
            raise ValueError(f"Hiányzó analysis mező: {key}")

    required_output = ["folder"]
    for key in required_output:
        if key not in config["output"]:
            raise ValueError(f"Hiányzó output mező: {key}")


def prepare_output_folder(config: dict) -> Path:
    output_folder = Path(config["output"]["folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    return output_folder


def print_project_summary(config: dict, output_folder: Path) -> None:
    print("\n=== Projekt összegzés ===")
    print(f"Projekt neve: {config['project_name']}")
    print(f"Helyszín: {config['location']['name']}")
    print(
        f"Koordináták: {config['location']['latitude']}, "
        f"{config['location']['longitude']}"
    )
    print(f"Vizsgálati sugár (km): {config['area_of_interest']['buffer_km']}")
    print(
        f"Időszak: {config['time_range']['start_date']} → "
        f"{config['time_range']['end_date']}"
    )
    print(f"Adatforrás: {config['data_source']['satellite']}")
    print(f"Max. felhőborítottság: {config['data_source']['cloud_cover_max']}%")
    print(f"Elemzés típusa: {config['analysis']['type']}")
    print(f"Felbontás: {config['analysis']['output_resolution_m']} m")
    print(f"Kimeneti mappa: {output_folder.resolve()}")
    print("=========================\n")


def main() -> None:
    try:
        config = load_config("config.yaml")
        validate_config(config)
        output_folder = prepare_output_folder(config)

        print_project_summary(config, output_folder)

        bbox = build_bounding_box(config)
        print_bounding_box_summary(bbox)

        aoi_file = save_aoi_to_json(bbox, output_folder)
        print_save_confirmation(aoi_file)

        aoi = load_aoi(aoi_file)
        data_request = build_data_request(config, aoi)
        data_request_file = save_data_request(data_request, output_folder)
        print_data_request_summary(data_request, data_request_file)

        download_result = fetch_true_color_preview(config, aoi, output_folder)
        print_download_summary(download_result)

        print("AOI sikeresen létrehozva és elmentve.")
        print("Adatlekérés előkészítve.")
        print("Valódi műholdkép sikeresen letöltve.")

    except Exception as error:
        print(f"Hiba: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
