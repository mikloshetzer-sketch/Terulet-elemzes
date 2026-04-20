from math import cos, radians
from typing import Dict


def km_to_latitude_degrees(km: float) -> float:
    return km / 111.32


def km_to_longitude_degrees(km: float, latitude: float) -> float:
    latitude_rad = radians(latitude)
    longitude_km_per_degree = 111.32 * cos(latitude_rad)

    if longitude_km_per_degree == 0:
        raise ValueError("A hosszúsági fok nem számolható ezen a szélességen.")

    return km / longitude_km_per_degree


def build_bounding_box(config: Dict) -> Dict:
    latitude = float(config["location"]["latitude"])
    longitude = float(config["location"]["longitude"])
    buffer_km = float(config["area_of_interest"]["buffer_km"])

    lat_offset = km_to_latitude_degrees(buffer_km)
    lon_offset = km_to_longitude_degrees(buffer_km, latitude)

    bbox = {
        "center": {
            "name": config["location"]["name"],
            "latitude": latitude,
            "longitude": longitude,
        },
        "buffer_km": buffer_km,
        "min_lat": latitude - lat_offset,
        "max_lat": latitude + lat_offset,
        "min_lon": longitude - lon_offset,
        "max_lon": longitude + lon_offset,
    }

    return bbox


def print_bounding_box_summary(bbox: Dict) -> None:
    print("\n=== Vizsgálati terület (AOI) ===")
    print(f"Helyszín: {bbox['center']['name']}")
    print(
        f"Középpont: {bbox['center']['latitude']}, "
        f"{bbox['center']['longitude']}"
    )
    print(f"Buffer: {bbox['buffer_km']} km")
    print(f"min_lat: {bbox['min_lat']:.6f}")
    print(f"max_lat: {bbox['max_lat']:.6f}")
    print(f"min_lon: {bbox['min_lon']:.6f}")
    print(f"max_lon: {bbox['max_lon']:.6f}")
    print("===============================\n")
