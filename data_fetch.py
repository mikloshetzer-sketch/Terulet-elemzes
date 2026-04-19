import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse

import requests


STAC_BASE_URL = "https://stac.dataspace.copernicus.eu/v1"
STAC_SEARCH_URL = f"{STAC_BASE_URL}/search"


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
        "comparison": config.get("comparison", {}),
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
        f"Fő időszak: {request['time_range']['start_date']} → "
        f"{request['time_range']['end_date']}"
    )

    comparison = request.get("comparison", {})
    if comparison.get("before") and comparison.get("after"):
        print(
            f"Before: {comparison['before']['start_date']} → "
            f"{comparison['before']['end_date']}"
        )
        print(
            f"After: {comparison['after']['start_date']} → "
            f"{comparison['after']['end_date']}"
        )

    print(f"Felhőborítottság max.: {request['data_source']['cloud_cover_max']}%")
    print(f"Elemzés típusa: {request['analysis']['type']}")
    print(f"Kimeneti fájl: {output_file.resolve()}")
    print("==============================\n")


def build_stac_search_params(
    config: Dict,
    aoi: Dict,
    start_date: str,
    end_date: str,
) -> Dict[str, str]:
    bbox = ",".join(
        [
            str(aoi["min_lon"]),
            str(aoi["min_lat"]),
            str(aoi["max_lon"]),
            str(aoi["max_lat"]),
        ]
    )

    params = {
        "bbox": bbox,
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "collections": "sentinel-2-l2a",
        "limit": "10",
    }
    return params


def search_sentinel_data(
    config: Dict,
    aoi: Dict,
    start_date: str,
    end_date: str,
) -> Dict:
    params = build_stac_search_params(config, aoi, start_date, end_date)

    response = requests.get(
        STAC_SEARCH_URL,
        params=params,
        timeout=60,
        headers={"User-Agent": "area-analysis-pipeline/1.0"},
    )

    if response.status_code != 200:
        full_url = f"{STAC_SEARCH_URL}?{urlencode(params)}"
        raise RuntimeError(
            f"Hiba a STAC lekérdezésnél. "
            f"HTTP {response.status_code}: {response.text}\n"
            f"Használt URL: {full_url}"
        )

    data = response.json()

    if "features" not in data:
        raise ValueError("A STAC válasz nem tartalmaz 'features' mezőt.")

    if not data["features"]:
        raise RuntimeError(
            f"Nincs találat a megadott paraméterekre: {start_date} → {end_date}"
        )

    all_features = sorted(
        data["features"],
        key=lambda feature: feature.get("properties", {}).get("eo:cloud_cover", 100),
    )

    max_cloud = config["data_source"]["cloud_cover_max"]
    filtered = [
        feature
        for feature in all_features
        if feature.get("properties", {}).get("eo:cloud_cover", 100) <= max_cloud
    ]

    if filtered:
        best_feature = filtered[0]
        best_feature["_selection_info"] = {
            "mode": "strict",
            "cloud_threshold": max_cloud,
            "matched_threshold": True,
        }
        return best_feature

    fallback_feature = all_features[0]
    fallback_cloud = fallback_feature.get("properties", {}).get("eo:cloud_cover", 100)
    fallback_feature["_selection_info"] = {
        "mode": "fallback_best_available",
        "cloud_threshold": max_cloud,
        "matched_threshold": False,
        "selected_cloud_cover": fallback_cloud,
    }

    print(
        f"Figyelem: nincs {max_cloud}% alatti találat a "
        f"{start_date} → {end_date} időszakban. "
        f"A legjobb elérhető jelenet lesz használva ({fallback_cloud}%)."
    )

    return fallback_feature


def save_stac_result(feature: Dict, output_folder: Path, label: str) -> Path:
    output_file = output_folder / f"stac_result_{label}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(feature, file, indent=4, ensure_ascii=False)

    return output_file


def build_download_result(feature: Dict, label: str) -> Dict:
    properties = feature.get("properties", {})
    assets = feature.get("assets", {})
    selection_info = feature.get("_selection_info", {})

    result = {
        "label": label,
        "status": "found",
        "id": feature.get("id"),
        "collection": feature.get("collection"),
        "datetime": properties.get("datetime"),
        "cloud_cover": properties.get("eo:cloud_cover"),
        "assets": list(assets.keys()),
        "selection_info": selection_info,
    }

    return result


def save_download_result(result: Dict, output_folder: Path, label: str) -> Path:
    output_file = output_folder / f"download_result_{label}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    return output_file


def print_stac_result_summary(feature: Dict, result_file: Path, label: str) -> None:
    properties = feature.get("properties", {})
    selection_info = feature.get("_selection_info", {})

    print(f"\n=== Valódi STAC találat ({label}) ===")
    print(f"ID: {feature.get('id')}")
    print(f"Kollekció: {feature.get('collection')}")
    print(f"Dátum: {properties.get('datetime')}")
    print(f"Felhőborítottság: {properties.get('eo:cloud_cover')}%")
    print(f"Kiválasztási mód: {selection_info.get('mode', 'unknown')}")
    print(f"Mentve ide: {result_file.resolve()}")
    print("====================================\n")


def print_download_summary(result: Dict, output_file: Path) -> None:
    selection_info = result.get("selection_info", {})

    print(f"\n=== Letöltési összegzés ({result['label']}) ===")
    print(f"Státusz: {result['status']}")
    print(f"Jelenet azonosító: {result['id']}")
    print(f"Dátum: {result['datetime']}")
    print(f"Felhőborítottság: {result['cloud_cover']}%")
    print(f"Kiválasztási mód: {selection_info.get('mode', 'unknown')}")
    print(f"Elérhető assetek: {', '.join(result['assets'])}")
    print(f"Kimeneti fájl: {output_file.resolve()}")
    print("====================================\n")


def select_preview_asset(feature: Dict) -> Tuple[str, Dict]:
    assets = feature.get("assets", {})

    preferred_keys = [
        "rendered_preview",
        "visual",
        "thumbnail",
        "overview",
        "preview",
    ]

    for key in preferred_keys:
        asset = assets.get(key)
        if asset and asset.get("href"):
            return key, asset

    for key, asset in assets.items():
        href = asset.get("href", "")
        if href.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return key, asset

    raise RuntimeError(
        "Nem található közvetlen preview asset a STAC találatban. "
        f"Elérhető assetek: {', '.join(assets.keys())}"
    )


def guess_extension(asset: Dict, url: str, content_type: Optional[str]) -> str:
    if content_type:
        normalized = content_type.lower()
        if "image/jpeg" in normalized:
            return ".jpg"
        if "image/png" in normalized:
            return ".png"
        if "image/webp" in normalized:
            return ".webp"

    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix

    asset_type = str(asset.get("type", "")).lower()
    if "jpeg" in asset_type:
        return ".jpg"
    if "png" in asset_type:
        return ".png"
    if "webp" in asset_type:
        return ".webp"

    return ".jpg"


def download_preview_image(feature: Dict, output_folder: Path, label: str) -> Dict:
    asset_key, asset = select_preview_asset(feature)
    url = asset["href"]

    response = requests.get(
        url,
        timeout=120,
        stream=True,
        headers={"User-Agent": "area-analysis-pipeline/1.0"},
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Hiba a preview kép letöltésénél. "
            f"HTTP {response.status_code}: {response.text[:300]}"
        )

    content_type = response.headers.get("Content-Type")
    extension = guess_extension(asset, url, content_type)
    output_file = output_folder / f"preview_{label}{extension}"

    with output_file.open("wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    result = {
        "label": label,
        "status": "downloaded",
        "asset_key": asset_key,
        "source_url": url,
        "content_type": content_type,
        "output_file": str(output_file),
        "file_size_bytes": output_file.stat().st_size,
    }

    result_file = output_folder / f"preview_download_{label}.json"
    with result_file.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    return result


def print_preview_download_summary(result: Dict) -> None:
    print(f"\n=== Preview kép letöltve ({result['label']}) ===")
    print(f"Asset kulcs: {result['asset_key']}")
    print(f"Tartalomtípus: {result['content_type']}")
    print(f"Fájlméret: {result['file_size_bytes']} bájt")
    print(f"Kimeneti fájl: {Path(result['output_file']).resolve()}")
    print("====================================\n")


def get_comparison_ranges(config: Dict) -> Dict[str, Dict[str, str]]:
    comparison = config.get("comparison")

    if not comparison:
        raise ValueError("Hiányzik a 'comparison' blokk a config.yaml fájlból.")

    if "before" not in comparison or "after" not in comparison:
        raise ValueError("A comparison blokkban kell 'before' és 'after' rész.")

    for label in ["before", "after"]:
        if "start_date" not in comparison[label] or "end_date" not in comparison[label]:
            raise ValueError(
                f"Hiányzó start_date vagy end_date a comparison/{label} részben."
            )

    return comparison
