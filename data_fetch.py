import json
import os
from pathlib import Path
from typing import Dict, Tuple

from sentinelhub import (
    BBox,
    CRS,
    DataCollection,
    MimeType,
    SentinelHubRequest,
    SHConfig,
    bbox_to_dimensions,
)


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


def get_sentinelhub_config() -> SHConfig:
    """
    Sentinel Hub konfiguráció környezeti változókból.
    Kötelező:
      - SENTINELHUB_CLIENT_ID
      - SENTINELHUB_CLIENT_SECRET

    Opcionális:
      - SENTINELHUB_BASE_URL
      - SENTINELHUB_AUTH_BASE_URL
    """
    client_id = os.getenv("SENTINELHUB_CLIENT_ID")
    client_secret = os.getenv("SENTINELHUB_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "Hiányzik a Sentinel Hub hitelesítés. "
            "Állítsd be a SENTINELHUB_CLIENT_ID és "
            "SENTINELHUB_CLIENT_SECRET környezeti változókat."
        )

    config = SHConfig()
    config.sh_client_id = client_id
    config.sh_client_secret = client_secret

    base_url = os.getenv("SENTINELHUB_BASE_URL")
    auth_base_url = os.getenv("SENTINELHUB_AUTH_BASE_URL")

    if base_url:
        config.sh_base_url = base_url

    if auth_base_url:
        config.sh_token_url = auth_base_url

    return config


def aoi_to_bbox(aoi: Dict) -> BBox:
    return BBox(
        bbox=(aoi["min_lon"], aoi["min_lat"], aoi["max_lon"], aoi["max_lat"]),
        crs=CRS.WGS84,
    )


def get_dimensions(aoi: Dict, resolution_m: int) -> Tuple[int, int]:
    bbox = aoi_to_bbox(aoi)
    return bbox_to_dimensions(bbox, resolution=resolution_m)


def get_true_color_evalscript() -> str:
    return """
//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04", "dataMask"],
    output: { bands: 4, sampleType: "AUTO" }
  };
}

function evaluatePixel(sample) {
  return [sample.B04, sample.B03, sample.B02, sample.dataMask];
}
"""


def fetch_true_color_preview(config_dict: Dict, aoi: Dict, output_folder: Path) -> Dict:
    satellite = config_dict["data_source"]["satellite"].lower()

    if satellite != "sentinel-2":
        raise ValueError(
            f"Jelenleg csak a 'sentinel-2' támogatott, kapott érték: {satellite}"
        )

    cloud_cover_max = config_dict["data_source"]["cloud_cover_max"]
    resolution_m = config_dict["analysis"]["output_resolution_m"]
    time_interval = (
        config_dict["time_range"]["start_date"],
        config_dict["time_range"]["end_date"],
    )

    sh_config = get_sentinelhub_config()
    bbox = aoi_to_bbox(aoi)
    size = get_dimensions(aoi, resolution_m)

    request = SentinelHubRequest(
        evalscript=get_true_color_evalscript(),
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=time_interval,
                maxcc=cloud_cover_max / 100.0,
            )
        ],
        responses=[
            SentinelHubRequest.output_response("default", MimeType.PNG)
        ],
        bbox=bbox,
        size=size,
        config=sh_config,
        data_folder=str(output_folder),
    )

    data = request.get_data(save_data=True)

    if not data:
        raise RuntimeError("Nem érkezett adat a Sentinel Hub lekérdezésből.")

    preview_file = output_folder / "true_color_preview.png"
    downloaded_files = sorted(output_folder.rglob("response.png"))

    if not downloaded_files:
        raise FileNotFoundError(
            "A Sentinel Hub válaszképe nem található az output mappában."
        )

    downloaded_files[-1].replace(preview_file)

    result = {
        "status": "downloaded",
        "satellite": "sentinel-2-l2a",
        "time_range": {
            "start_date": time_interval[0],
            "end_date": time_interval[1],
        },
        "cloud_cover_max": cloud_cover_max,
        "resolution_m": resolution_m,
        "image_size_px": {
            "width": size[0],
            "height": size[1],
        },
        "output_file": str(preview_file),
    }

    metadata_file = output_folder / "download_result.json"
    with metadata_file.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    return result


def print_download_summary(result: Dict) -> None:
    print("\n=== Valódi műholdkép lekérve ===")
    print(f"Forrás: {result['satellite']}")
    print(
        f"Időszak: {result['time_range']['start_date']} → "
        f"{result['time_range']['end_date']}"
    )
    print(f"Max. felhőborítottság: {result['cloud_cover_max']}%")
    print(
        f"Képméret: {result['image_size_px']['width']} x "
        f"{result['image_size_px']['height']} px"
    )
    print(f"Kimeneti fájl: {Path(result['output_file']).resolve()}")
    print("================================\n")
