"""Formatting helpers."""

import re
from datetime import datetime


def format_size(num: float, decimals: int = 1) -> str:
    if num is None:
        return "0 B"
    num = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num) < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{int(num)} B"
            return f"{num:.{decimals}f} {unit}"
        num /= 1024.0
    return f"{num:.{decimals}f} PB"


def parse_size(text: str) -> int:
    text = text.strip().upper().replace(" ", "")
    match = re.match(r"^([\d.]+)([KMGT]?I?B?)$", text)
    if not match:
        raise ValueError(f"Invalid size: {text!r}")
    value = float(match.group(1))
    unit = match.group(2)
    multipliers = {
        "": 1,
        "B": 1,
        "KB": 1024,
        "KIB": 1024,
        "MB": 1024**2,
        "MIB": 1024**2,
        "GB": 1024**3,
        "GIB": 1024**3,
        "TB": 1024**4,
        "TIB": 1024**4,
    }
    if unit not in multipliers:
        raise ValueError(f"Invalid size unit: {unit!r}")
    return int(value * multipliers[unit])


def format_duration(seconds: float) -> str:
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    if minutes < 60:
        return f"{minutes}m {rest:.0f}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


def format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d %H:%M")


def bytes_from_mtime(ts: float) -> datetime:
    return datetime.fromtimestamp(ts)
