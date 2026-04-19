import json
from pathlib import Path
from typing import Dict

import requests


def load_aoi(aoi_path: str = "output/aoi.json") -> Dict:
    path = Path(aoi_path)

    if not path.exists():
        raise FileNotFoundError(f"Hiányzik az AOI fájl: {aoi_path}")

    with path.open("r", encoding="utf-8") as file:
        aoi = json.load(file)

    if not isinstance(aoi, dict):
        raise ValueError("Az AOI fájl tartalma nem értelmezhető szótárként.")

    return aoi


def build_data_request(config: Dict, aoi: Dict) -> Dict:
    request = {
        "project_name": config["project_name"],
        "location_name": config["location"]["name"],
        "data_source": {
            "satellite": config["data_source"]["satellite"],
            "cloud_cover_max": config["data_source"]["cloud_cover_max"],
        },
        "time_range": {
            "start_date": config["time_range"]["start_date"],
            "end_date": config["time_range"]["end_date"],
        },
        "analysis": {
            "type": config["analysis"]["type"],
            "output_resolution_m": config["analysis"]["output_resolution_m"],
        },
        "aoi": aoi,
        "status": "prepared",
    }

    return request


def save_data_request(request: Dict, output_folder: Path) -> Path:
    output_file = output_folder / "data_request.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(request, file, indent=4, ensure_ascii=False)

    return output_file


def print_data_request_summary(request: Dict, output_file: Path) -> None:
    print("\n=== Adatlekérés előkészítve ===")
    print(f"Projekt: {request['project_name']}")
    print(f"Helyszín: {request['location_name']}")
    print(f"Műholdforrás: {request['data_source']['satellite']}")
    print(
        f"Időszak: {request['time_range']['start_date']} → "
        f"{request['time_range']['end_date']}"
    )
    print(f"Felhőborítottság max.: {request['data_source']['cloud_cover_max']}%")
    print(f"Elemzés típusa: {request['analysis']['type']}")
    print(f"Kimeneti fájl: {output_file.resolve()}")
    print("==============================\n")


def build_stac_search_payload(config: Dict, aoi: Dict) -> Dict:
    bbox = [
        aoi["min_lon"],
        aoi["min_lat"],
        aoi["max_lon"],
        aoi["max_lat"],
    ]

    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "limit": 5,
        "datetime": (
            f"{config['time_range']['start_date']}/"
            f"{config['time_range']['end_date']}"
        ),
        "query": {
            "eo:cloud_cover": {
                "lt": config["data_source"]["cloud_cover_max"]
            }
        },
    }

    return payload


def search_sentinel_data(config: Dict, aoi: Dict) -> Dict:
    url = "https://catalogue.dataspace.copernicus.eu/stac/search"
    payload = build_stac_search_payload(config, aoi)

    response = requests.post(url, json=payload, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"Hiba a STAC lekérdezésnél. "
            f"HTTP {response.status_code}: {response.text}"
        )

    data = response.json()

    if "features" not in data:
        raise ValueError("A STAC válasz nem tartalmaz 'features' mezőt.")

    if not data["features"]:
        raise RuntimeError("Nincs találat a megadott paraméterekre.")

    return data["features"][0]


def save_stac_result(feature: Dict, output_folder: Path) -> Path:
    output_file = output_folder / "stac_result.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(feature, file, indent=4, ensure_ascii=False)

    return output_file


def build_download_result(feature: Dict) -> Dict:
    properties = feature.get("properties", {})
    assets = feature.get("assets", {})

    result = {
        "status": "found",
        "id": feature.get("id"),
        "collection": feature.get("collection"),
        "datetime": properties.get("datetime"),
        "cloud_cover": properties.get("eo:cloud_cover"),
        "assets": list(assets.keys()),
    }

    return result


def save_download_result(result: Dict, output_folder: Path) -> Path:
    output_file = output_folder / "download_result.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    return output_file


def print_stac_result_summary(feature: Dict, result_file: Path) -> None:
    properties = feature.get("properties", {})

    print("\n=== Valódi STAC találat ===")
    print(f"ID: {feature.get('id')}")
    print(f"Kollekció: {feature.get('collection')}")
    print(f"Dátum: {properties.get('datetime')}")
    print(f"Felhőborítottság: {properties.get('eo:cloud_cover')}%")
    print(f"Mentve ide: {result_file.resolve()}")
    print("===========================\n")


def print_download_summary(result: Dict, output_file: Path) -> None:
    print("\n=== Letöltési összegzés ===")
    print(f"Státusz: {result['status']}")
    print(f"Jelenet azonosító: {result['id']}")
    print(f"Dátum: {result['datetime']}")
    print(f"Felhőborítottság: {result['cloud_cover']}%")
    print(f"Elérhető assetek: {', '.join(result['assets'])}")
    print(f"Kimeneti fájl: {output_file.resolve()}")
    print("===========================\n")
