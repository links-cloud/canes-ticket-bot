from pathlib import Path
from dataclasses import dataclass
from typing import List
import yaml


@dataclass
class Game:
    id: str
    label: str
    date: str
    lower_threshold: float
    upper_threshold: float
    sro_threshold: float


@dataclass
class Config:
    team: str
    venue: str
    venue_city: str
    games: List[Game]
    lower_prefixes: List[str]
    upper_prefixes: List[str]
    send_repeat_alerts: bool


def load(path: str = "config.yaml") -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    games = [
        Game(
            id=g["id"],
            label=g["label"],
            date=g["date"],
            lower_threshold=float(g["thresholds"]["lower"]),
            upper_threshold=float(g["thresholds"]["upper"]),
            sro_threshold=float(
                g["thresholds"].get("sro", g["thresholds"]["upper"])
            ),
        )
        for g in raw["games"]
    ]
    return Config(
        team=raw["team"],
        venue=raw["venue"],
        venue_city=raw["venue_city"],
        games=games,
        lower_prefixes=raw["section_classification"]["lower_sections"],
        upper_prefixes=raw["section_classification"]["upper_sections"],
        send_repeat_alerts=bool(raw.get("send_repeat_alerts", False)),
    )
