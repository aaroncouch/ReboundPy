from typing import Any
from dataclasses import fields

from src.models import Player

def normalize_player_stats(player_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes player statistics by converting numeric strings to integers,
    replacing empty strings with zeros, and substituting '*' with 1.

    Args:
        player_data (dict[Any, Any]): A dictionary containing player statistics.

    Returns:
        dict[Any, Any]: A new dictionary with normalized values.
    """
    normalized = {}
    for key, value in player_data.items():
        if isinstance(value, str):
            if value.isdigit():
                normalized[key] = int(value)
            # Replace empty strings with zero
            elif value == "":
                normalized[key] = 0
            # Replace '*' with 1
            elif value == "*":
                normalized[key] = 1
            # Keep other strings as-is
            else:
                normalized[key] = value
        else:
            # Preserve non-string values as-is
            normalized[key] = value
    return normalized

def map_player_headers_to_player_fields(cls: Player, data: dict[str: Any]) -> dict[str, Any]:
    header_to_field = {
        field.metadata["header"]: field.name
        for field in fields(cls)
        if "header" in field.metadata
    }
    return {
        header_to_field.get(key, key): value
        for key, value in data.items()
    }