import hashlib
import json
import re

from models import Action, GameState


class Perception:
    def parse(self, text: str, buttons=None) -> GameState:
        text = text or ""
        state = GameState(raw_text=text)
        state.location = self._detect_location(text)
        state.current_action = self._parse_current_action(text)
        state.self_data = self._parse_creature(text, "Вы")
        state.enemy_data = self._parse_creature(text, "Вражеские существа")
        state.inventory = self._parse_inventory(text)
        state.events = self._parse_events(text)
        state.available_actions = self._parse_buttons(buttons or [])
        return state

    def state_key(self, state: GameState) -> str:
        data = {
            "location": state.location,
            "current_action": state.current_action,
            "self": self._normalize_creature(state.self_data),
            "enemy": self._normalize_creature(state.enemy_data),
            "inventory": state.inventory,
            "events": state.events[-5:],
            "actions": sorted(action.key or action.text for action in state.available_actions),
        }
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _detect_location(self, text: str) -> str:
        checks = {
            "battle": ("Каков ваш приказ?", "наносит", "Вражеские существа", "Атаковать"),
            "exploration": ("Исследуя", "Дальность исследования", "исследовани"),
            "profile": ("Профиль", "Уровень:", "Опыт:"),
            "skills": ("Основное", "Сила", "Ловкость", "Атлетика"),
            "inventory": ("Инвентарь", "Макс. вес", "Вес:"),
            "city": ("Город",),
        }
        for location, markers in checks.items():
            if sum(marker.lower() in text.lower() for marker in markers) >= 1:
                return location
        return "unknown"

    def _parse_current_action(self, text: str) -> str:
        patterns = (
            r"(?:Текущее действие|Текущее занятие|Действие)\s*:\s*(.+)",
            r"(?:Сейчас|В данный момент)\s*:\s*(.+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().splitlines()[0]
        return "unknown"

    def _parse_creature(self, text: str, section: str) -> dict:
        result = {}
        marker = text.find(section)
        if marker < 0:
            return result
        chunk = text[marker:]

        patterns = {
            "level": r"(?:Уровень|уровень)\s*[:№]?\s*(\d+)",
            "experience": r"(?:Опыт|опыт)\s*[:№]?\s*(\d+)\s*(?:/\s*(\d+))?",
            "hp": r"(?:Здоровье|HP|ХП|Состояние)\s*[:№]?\s*(\d+)\s*(?:/\s*(\d+))?",
            "hunger": r"(?:Голод)\s*[:№]?\s*(\d+)\s*(?:/\s*(\d+))?",
            "water": r"(?:Вода)\s*[:№]?\s*(\d+)\s*(?:/\s*(\d+))?",
            "weight": r"(?:Вес)\s*[:№]?\s*([\d.,]+)\s*(?:/\s*([\d.,]+))?",
        }
        for name, pattern in patterns.items():
            match = re.search(pattern, chunk, re.IGNORECASE)
            if match:
                result[name] = self._number(match.group(1))
                if match.group(2):
                    result[f"{name}_max"] = self._number(match.group(2))

        species = re.search(r"(?:Вид|Вид существа|Порода)\s*:\s*([^\n]+)", chunk, re.IGNORECASE)
        if species:
            result["species"] = species.group(1).strip()

        name = re.search(r"(?:Имя|Имя существа)\s*:\s*([^\n]+)", chunk, re.IGNORECASE)
        if name:
            result["name"] = name.group(1).strip()

        body_match = re.search(r"\[([💀🪲🪱⚔;\d\s]+)\]", chunk)
        if body_match:
            result["body_raw"] = body_match.group(1).strip()

        return result

    def _parse_inventory(self, text: str) -> dict[str, int]:
        inventory = {}
        marker = text.lower().find("инвентарь")
        if marker < 0:
            return inventory
        chunk = text[marker:]
        for line in chunk.splitlines()[1:]:
            match = re.match(r"\s*([^:—-]{2,40})\s*[:—-]\s*(\d+)\s*$", line)
            if not match:
                continue
            name = match.group(1).strip()
            if name.lower() in {"вес", "макс. вес", "максимальный вес"}:
                continue
            inventory[name] = int(match.group(2))
        return inventory

    def _parse_events(self, text: str) -> list[str]:
        events = []
        markers = (
            "победил", "побежден", "погиб", "проиграл", "теряет сознание",
            "получил", "получено", "нашел", "найден", "получен", "уровень повышен",
        )
        for line in text.splitlines():
            line = line.strip()
            if line and any(marker in line.lower() for marker in markers):
                events.append(line)
        return events[-10:]

    def _normalize_creature(self, data: dict) -> dict:
        normalized = dict(data)
        hp = normalized.get("hp")
        hp_max = normalized.get("hp_max")
        if hp is not None and hp_max:
            normalized["hp_ratio"] = round(hp / hp_max, 3)
            normalized.pop("hp", None)
            normalized.pop("hp_max", None)
        hunger = normalized.get("hunger")
        hunger_max = normalized.get("hunger_max")
        if hunger is not None and hunger_max:
            normalized["hunger_ratio"] = round(hunger / hunger_max, 3)
            normalized.pop("hunger", None)
            normalized.pop("hunger_max", None)
        water = normalized.get("water")
        water_max = normalized.get("water_max")
        if water is not None and water_max:
            normalized["water_ratio"] = round(water / water_max, 3)
            normalized.pop("water", None)
            normalized.pop("water_max", None)
        return normalized

    def _number(self, value: str):
        value = value.replace(",", ".")
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except ValueError:
            return value

    def _parse_buttons(self, buttons) -> list[Action]:
        result = []
        for button in buttons:
            if isinstance(button, Action):
                result.append(button)
                continue
            text = getattr(button, "text", str(button))
            callback_data = getattr(button, "data", None)
            if isinstance(callback_data, bytes):
                callback_data = callback_data.decode("utf-8", errors="replace")
            result.append(Action(text=text, callback_data=callback_data, key=text.strip().lower()))
        return result
