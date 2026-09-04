class RewardEngine:
    def calculate(self, before, after, action: str = "", stagnation_steps: int = 0) -> float:
        reward = 0.0
        before_text = before.raw_text.lower()
        after_text = after.raw_text.lower()
        action_text = (action or "").strip().lower()

        reward += self._numeric_delta(before.self_data, after.self_data, "experience", 0.02)
        reward += self._numeric_delta(before.self_data, after.self_data, "level", 10.0)
        reward += self._numeric_delta(before.self_data, after.self_data, "hp", 0.08)
        reward += self._numeric_delta(before.self_data, after.self_data, "hunger", -0.01)
        reward += self._numeric_delta(before.self_data, after.self_data, "water", -0.01)

        reward += self._numeric_delta(before.enemy_data, after.enemy_data, "hp", -0.08)
        reward += self._body_part_delta(before.self_data, after.self_data, 0.12)
        reward += self._body_part_delta(before.enemy_data, after.enemy_data, -0.12)
        reward += self._skill_delta(before.self_data, after.self_data)
        reward += self._inventory_delta(before.inventory, after.inventory)

        if "все враги повержены" in after_text:
            reward += 30.0
        if "теряет сознание" in after_text:
            reward += 12.0
        if "побежден" in after_text or "победил" in after_text:
            reward += 25.0
        if "все враги повержены" not in after_text and ("погиб" in after_text or "проиграл" in after_text):
            reward -= 100.0
        if ("нашел" in after_text or "найдены предметы" in after_text or "найден предмет" in after_text) and "не было найдено" not in after_text:
            reward += 5.0

        if after.events and after.events != before.events:
            reward += 1.0

        if stagnation_steps > 0 and before.location == after.location:
            reward -= min(stagnation_steps, 5) * 0.10

        reward += self._action_shaping(before, after, action_text)
        return reward

    def _action_shaping(self, before, after, action: str) -> float:
        if not action:
            return 0.0

        if action == "атаковать":
            before_enemy_hp = before.enemy_data.get("hp")
            after_enemy_hp = after.enemy_data.get("hp")
            if (
                isinstance(before_enemy_hp, (int, float))
                and isinstance(after_enemy_hp, (int, float))
                and after_enemy_hp < before_enemy_hp
            ):
                return 0.25
            if after.location == "battle":
                return 0.05
            return -0.25

        if action in {"общение", "состояние (вы)", "состояние (враг)", "предметы", "снаряжение"}:
            if after.location == before.location:
                return -0.05
            return 0.0

        if action == "отступить":
            if before.location == "battle" and after.location != "battle":
                return -0.5
            return -0.10

        if action in {"назад", "🔙назад", "🔙меню"}:
            return -0.02

        return 0.0

    def _numeric_delta(self, before, after, key: str, multiplier: float) -> float:
        before_value = before.get(key)
        after_value = after.get(key)
        if not isinstance(before_value, (int, float)) or not isinstance(after_value, (int, float)):
            return 0.0
        return (after_value - before_value) * multiplier

    def _body_part_delta(self, before, after, multiplier: float) -> float:
        before_parts = before.get("body_parts", {})
        after_parts = after.get("body_parts", {})
        reward = 0.0
        for part, value in after_parts.items():
            if part.endswith("_max"):
                continue
            previous = before_parts.get(part)
            if not isinstance(previous, (int, float)) or not isinstance(value, (int, float)):
                continue
            reward += (value - previous) * multiplier
        return reward

    def _skill_delta(self, before, after) -> float:
        before_skills = before.get("skills", {})
        after_skills = after.get("skills", {})
        reward = 0.0
        for skill, value in after_skills.items():
            previous = before_skills.get(skill)
            if isinstance(previous, (int, float)) and isinstance(value, (int, float)) and value > previous:
                reward += (value - previous) * 4.0
        return reward

    def _inventory_delta(self, before, after) -> float:
        reward = 0.0
        for item, value in after.items():
            previous = before.get(item, 0)
            if value > previous:
                reward += min(value - previous, 10) * 1.5
            elif value < previous:
                reward -= min(previous - value, 10) * 0.5
        return reward
