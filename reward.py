class RewardEngine:
    def calculate(self, before, after) -> float:
        reward = 0.0
        before_text = before.raw_text
        after_text = after.raw_text

        if "Все враги повержены" in after_text:
            reward += 20.0
        if "теряет сознание" in after_text.lower():
            reward += 10.0
        if "побежден" in after_text.lower() or "победил" in after_text.lower():
            reward += 20.0
        if "погиб" in after_text.lower() or "проиграл" in after_text.lower():
            reward -= 100.0

        reward += self._damage_reward(before_text, after_text)
        return reward

    def _damage_reward(self, before_text: str, after_text: str) -> float:
        return 0.0
