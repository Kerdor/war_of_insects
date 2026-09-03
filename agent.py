import asyncio

from learning import QLearning
from memory import ExperienceMemory
from perception import Perception
from reward import RewardEngine
from transitions import TransitionMemory


class Agent:
    def __init__(self, learning=None, memory=None, transitions=None):
        self.perception = Perception()
        self.learning = learning or QLearning()
        self.memory = memory or ExperienceMemory()
        self.transitions = transitions or TransitionMemory()
        self.reward = RewardEngine()
        self.epsilon = 0.20

    async def step(self, client, message, account_id):
        buttons = self._flatten_buttons(message)
        state = self.perception.parse(message.text or "", buttons)
        state_key = self.perception.state_key(state)
        actions = [action.key or action.text for action in state.available_actions]

        if not actions:
            return None

        selected_key = self.learning.choose(state_key, actions, self.epsilon, self.transitions)
        selected = next(action for action in state.available_actions if (action.key or action.text) == selected_key)

        await self._click(message, selected)
        next_message = await self._wait_for_change(client, state_key)
        if next_message is None:
            return selected.text

        next_state = self.perception.parse(next_message.text or "", self._flatten_buttons(next_message))
        next_key = self.perception.state_key(next_state)
        next_actions = [action.key or action.text for action in next_state.available_actions]
        reward = self.reward.calculate(state, next_state)

        self.memory.add(account_id, state_key, selected_key, next_key, reward)
        self.transitions.record(state_key, selected_key, next_key, reward)
        self.learning.update(state_key, selected_key, reward, next_key, next_actions)
        return selected.text

    async def _wait_for_change(self, client, state_key: str):
        for _ in range(10):
            await asyncio.sleep(0.5)
            message = await client.get_latest()
            if message is None:
                continue
            state = self.perception.parse(message.text or "", self._flatten_buttons(message))
            if self.perception.state_key(state) != state_key:
                return message
        return await client.get_latest()

    async def _click(self, message, action) -> None:
        if action.callback_data is not None:
            for row in message.buttons or []:
                for button in row:
                    data = getattr(button, "data", None)
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    if data == action.callback_data:
                        await button.click()
                        return
        for row in message.buttons or []:
            for button in row:
                if getattr(button, "text", "") == action.text:
                    await button.click()
                    return

    def _flatten_buttons(self, message):
        result = []
        for row in message.buttons or []:
            result.extend(row)
        return result
