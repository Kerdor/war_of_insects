import re
import hashlib
import json

from models import Action, GameState


class Perception:
    def parse(self, text: str, buttons=None) -> GameState:
        state = GameState(raw_text=text or "")
        state.location = self._detect_location(text or "")
        state.self_data = self._parse_creature(text or "", "Вы")
        state.enemy_data = self._parse_creature(text or "", "Вражеские существа")
        state.available_actions = self._parse_buttons(buttons or [])
        return state

    def state_key(self, state: GameState) -> str:
        data = {
            "location": state.location,
            "current_action": state.current_action,
            "self": state.self_data,
            "enemy": state.enemy_data,
            "inventory": state.inventory,
            "actions": sorted(action.key or action.text for action in state.available_actions),
        }
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _detect_location(self, text: str) -> str:
        checks = {
            "battle": ("Каков ваш приказ?", "наносит", "противник"),
            "exploration": ("Исследуя", "Дальность исследования"),
            "city": ("Город",),
        }
        for location, markers in checks.items():
            if any(marker in text for marker in markers):
                return location
        return "unknown"

    def _parse_creature(self, text: str, section: str) -> dict:
        result = {}
        marker = text.find(section)
        if marker < 0:
            return result
        chunk = text[marker:]
        hp_match = re.search(r"\[([💀🪲🪱⚔;\d]+)\]", chunk)
        if hp_match:
            result["body_raw"] = hp_match.group(1)
        return result

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
