# PROJECT STATE

## 2026-09-04 — Runtime error fixes

Fixed runtime errors found during multi-account startup/game loop testing.

### Fixes

`learning.py`:
- fixed unpacking of `TransitionMemory.predict()` result;
- transition prediction returns `(count, next_state, average_reward)`, and all three values are now unpacked correctly.

`main.py`:
- fixed cleanup check from nonexistent `GameClient.is_connected()` to the underlying Telethon client's `is_connected()`.

`agent.py` / `perception.py`:
- fixed `Start parameter invalid (caused by StartBotRequest)` caused by Telegram `KeyboardButtonSwitchInline` buttons being treated as normal game actions;
- SwitchInline buttons are now ignored by perception and skipped by the action click fallback;
- normal callback and reply-keyboard buttons remain supported.

### Multi-account behavior

- Enabled accounts still authorize sequentially.
- Already authorized sessions skip code entry.
- Enabled accounts run concurrently after authorization.
- Account enable flags remain supported through `ACCOUNT_N_ENABLED=true/false`.

### Current commits

- Config: `7d7b6ca139555a6dd6074d8946ff15dce765c4c0`
- Telegram authorization: `02833f912879a0ed839397d0a9ae66d54fe32af0`
- Main runtime cleanup fix: `7e66f63fa941b1c5fad937431c6fa7c60585a342`
- Learning transition unpack fix: `244e0ab7c7ee816fdd73d88522dfa6ceaa8a6164`
- Agent SwitchInline handling: `9fdc33b8d1c5223a736ac703c7231597366c41f5`
- Perception SwitchInline filtering: `f52e13d661f5d4840efeafd4b6f4f170a128cc7f`
