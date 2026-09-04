import hashlib
import json
import re

from telethon.tl.types import KeyboardButtonSwitchInline

from .models import Action, GameState


class Perception:
    def parse(self, text: str, buttons=None) -> GameState:
        text = text or ""
        state = GameState(raw_text=text)
        state.available_actions = self._parse_buttons(buttons or [])
        state.location = self._detect_location(text, state.available_actions)
        state.current_action = self._parse_current_action(text)
        state.self_data = self._parse_creature(text, "Вы")
        state.enemy_data = self._parse_creature(text, "Вражеские существа")
        state.inventory = self._parse_inventory(text)
        state.events = self._parse_events(text)
        return state

    def state_key(self, state: GameState) -> str:
        data = {
            "location": state.location,
            "current_action": self._normalize_action(state.current_action),
            "self": self._normalize_creature(state.self_data),
            "enemy": self._normalize_creature(state.enemy_data),
            "inventory": self._normalize_inventory(state.inventory),
            "events": self._normalize_events(state.events),
            "actions": sorted(action.key or action.text for action in state.available_actions),
        }
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _detect_location(self, text: str, actions=None) -> str:
        lowered = text.lower()
        button_texts = {action.text.strip().lower() for action in (actions or [])}

        battle_signature = (
            "каков ваш приказ?" in lowered
            or ("вражеские существа" in lowered and "атаковать" in lowered)
            or ("наносит" in lowered and "атаковать" in button_texts)
        )
        if battle_signature:
            return "battle"

        if self._has_any(button_texts, "🏜 ближайшие территории", "⛰ умеренная дальность", "🌋 дальние территории", "🔘 сбор отряда"):
            return "exploration"

        if self._has_any(button_texts, "🦾сила", "🪶ловкость", "🏃атлетика", "👁восприятие", "⚔атака", "🛡защита", "💨уклонение"):
            return "skills"

        if self._has_any(button_texts, "💀голова", "🪲грудь", "🪱живот", "🐾лапы", "📥снять всё", "📌шаблоны"):
            return "equipment"

        if self._has_any(button_texts, "🏕тайники", "🗺использовать", "🗄сейфы"):
            return "inventory"

        if self._has_any(button_texts, "⭐️задания", "💩кидайтесь", "🐜исследуйте в отряде", "🔥рейтинг", "⏳"):
            return "quests"

        if self._has_any(button_texts, "🔘далее") and self._has_any(
            button_texts,
            "🏞с чего начать новичку?",
            "🐜насекомые",
            "🏜исследование мира",
            "🗺предметы",
            "🔰кланы",
            "🏆турниры",
            "🐍отряд",
        ):
            return "tutorial"

        if self._has_any(button_texts, "🔙меню") and self._has_any(
            button_texts,
            "🏕тайник",
            "📦доставка",
            "📝инсектарий",
            "🏆турнир",
            "💵кредиты",
            "🎁бонус #1",
            "🎁бонус #2",
            "🎁бонус #3",
            "🏪лавка",
            "🕷рефералы",
        ):
            return "secondary_menu"

        if self._has_any(
            button_texts,
            "🏜исследовать",
            "⭐️задания",
            "🗞события",
            "🐾насекомое",
            "🍗состояние",
            "💰инвентарь",
            "⚔навыки",
            "🗡снаряжение",
        ):
            return "main"

        if "профиль" in lowered:
            return "profile"

        if "инвентарь" in lowered and ("вес:" in lowered or "макс. вес" in lowered):
            return "inventory"

        if "навыки" in lowered and any(marker in lowered for marker in ("сила", "ловкость", "атлетика", "восприятие")):
            return "skills"

        if "основное" in lowered and any(marker in lowered for marker in ("сила", "ловкость", "атлетика", "восприятие")):
            return "skills"

        if "город" in lowered and "каков ваш приказ?" not in lowered:
            return "city"

        if self._has_any(button_texts, "❓помощь", "💬официальный чат", "📖справочник", "💡идеи"):
            return "help"

        return "unknown"

    def _has_any(self, values: set[str], *markers: str) -> bool:
        return any(marker.lower() in values for marker in markers)

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
        chunk = self._section_chunk(text, section)
        if not chunk:
            return result

        patterns = {
            "level": r"(?:Уровень|уровень)\s*[:№]?\s*(\d+)",
            "experience": r"(?:Опыт|опыт)\s*[:№]?\s*(\d+)\s*(?:/\s*(\d+))?",
            "hp": r"(?:Здоровье|HP|ХП|Состояние)\s*[:№]?\s*(-?\d+)\s*(?:/\s*(-?\d+))?",
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

        result["body_parts"] = self._parse_body_parts(chunk)
        result["skills"] = self._parse_skills(chunk)
        return result

    def _section_chunk(self, text: str, section: str) -> str:
        marker = text.lower().find(section.lower())
        if marker < 0:
            return ""
        end_markers = (
            "вражеские существа",
            "инвентарь",
            "профиль",
            "навыки",
            "основное",
            "каков ваш приказ?",
        )
        end = len(text)
        for end_marker in end_markers:
            position = text.lower().find(end_marker, marker + len(section))
            if position >= 0 and position < end:
                end = position
        return text[marker:end]

    def _parse_body_parts(self, text: str) -> dict[str, int]:
        result = {}
        aliases = {
            "голова": "head",
            "голову": "head",
            "грудь": "chest",
            "живот": "abdomen",
            "брюшко": "abdomen",
        }
        for russian, key in aliases.items():
            match = re.search(rf"{re.escape(russian)}\s*[:—-]?\s*(-?\d+)(?:\s*/\s*(-?\d+))?", text, re.IGNORECASE)
            if match:
                result[key] = int(match.group(1))
                if match.group(2):
                    result[f"{key}_max"] = int(match.group(2))

        leg_patterns = (
            r"(?:нога|ноги|лапа|лапы)\s*(\d+)\s*[:—-]?\s*(-?\d+)",
            r"(?:нога|лапа)\s*#?\s*(\d+)\s*[:—-]?\s*(-?\d+)",
        )
        for pattern in leg_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                result[f"leg_{match.group(1)}"] = int(match.group(2))
        return result

    def _parse_skills(self, text: str) -> dict[str, int]:
        result = {}
        skills = (
            "Сила", "Ловкость", "Атлетика", "Восприятие",
            "Атака", "Защита", "Уклонение",
            "Режущее", "Рубящее", "Дробящее", "Колющее",
            "Скрытность", "Взлом", "Воровство",
            "Общее ремесло", "Ковка оружия", "Ковка брони", "Зельеварение", "Готовка",
            "Инженерия", "Медицина",
        )
        for skill in skills:
            match = re.search(rf"{re.escape(skill)}\s*[:—-]?\s*(\d+)", text, re.IGNORECASE)
            if match:
                result[skill.lower()] = int(match.group(1))
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
        normalized.pop("name", None)
        normalized["hp_state"] = self._ratio_bucket(normalized.pop("hp", None), normalized.pop("hp_max", None))
        normalized["hunger_state"] = self._ratio_bucket(normalized.pop("hunger", None), normalized.pop("hunger_max", None))
        normalized["water_state"] = self._ratio_bucket(normalized.pop("water", None), normalized.pop("water_max", None))
        normalized["weight_state"] = self._ratio_bucket(normalized.pop("weight", None), normalized.pop("weight_max", None))

        if "experience" in normalized:
            normalized["experience"] = self._experience_bucket(normalized["experience"], normalized.get("experience_max"))
            normalized.pop("experience_max", None)

        if "level" in normalized:
            normalized["level"] = self._level_bucket(normalized["level"])

        if "body_parts" in normalized:
            normalized["body_parts"] = self._normalize_body_parts(normalized["body_parts"])
        if "skills" in normalized:
            normalized["skills"] = self._normalize_skills(normalized["skills"])
        return normalized

    def _normalize_body_parts(self, parts: dict) -> dict:
        result = {}
        for key, value in parts.items():
            if key.endswith("_max"):
                continue
            maximum = parts.get(f"{key}_max")
            result[key] = self._ratio_bucket(value, maximum)
        return result

    def _normalize_skills(self, skills: dict) -> dict:
        return {key: self._level_bucket(value) for key, value in skills.items()}

    def _normalize_inventory(self, inventory: dict[str, int]) -> dict[str, str]:
        return {name: self._quantity_bucket(quantity) for name, quantity in inventory.items()}

    def _normalize_events(self, events: list[str]) -> list[str]:
        result = []
        for event in events[-5:]:
            lowered = event.lower()
            if "погиб" in lowered or "проиграл" in lowered:
                result.append("defeat")
            elif "теряет сознание" in lowered:
                result.append("unconscious")
            elif "победил" in lowered or "побежден" in lowered:
                result.append("victory")
            elif "уровень повышен" in lowered:
                result.append("level_up")
            elif "нашел" in lowered or "найден" in lowered or "получен" in lowered or "получено" in lowered:
                result.append("loot")
            elif "получил" in lowered:
                result.append("gain")
        return result

    def _normalize_action(self, action: str) -> str:
        return action.strip().lower() if action else "unknown"

    def _ratio_bucket(self, value, maximum) -> str:
        if value is None or maximum in (None, 0):
            return "unknown"
        ratio = value / maximum
        if ratio <= 0:
            return "empty"
        if ratio <= 0.25:
            return "critical"
        if ratio <= 0.50:
            return "low"
        if ratio <= 0.75:
            return "medium"
        return "high"

    def _experience_bucket(self, value, maximum) -> str:
        if maximum in (None, 0):
            return str(value)
        return self._ratio_bucket(value, maximum)

    def _level_bucket(self, value) -> str:
        if value <= 1:
            return "1"
        if value <= 3:
            return "2-3"
        if value <= 5:
            return "4-5"
        if value <= 10:
            return "6-10"
        return "11+"

    def _quantity_bucket(self, value) -> str:
        if value <= 0:
            return "0"
        if value <= 3:
            return "1-3"
        if value <= 10:
            return "4-10"
        return "11+"

    def _number(self, value: str):
        value = value.replace(",", ".")
        number = float(value)
        return int(number) if number.is_integer() else number

    def _parse_buttons(self, buttons) -> list[Action]:
        result = []
        for row in buttons:
            for button in row:
                text = getattr(button, "text", "") or ""
                if not text:
                    continue
                if isinstance(getattr(button, "button", None), KeyboardButtonSwitchInline):
                    continue
                callback_data = getattr(button, "data", None)
                if isinstance(callback_data, bytes):
                    callback_data = callback_data.decode("utf-8", errors="replace")
                result.append(Action(text=text, callback_data=callback_data, key=text))
        return result
