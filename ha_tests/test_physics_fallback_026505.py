"""0.26.5.5 (F05, FAIQ-LEARN-001): the physics fallback reaches every path that uses the learned rate.

When the learning effectiveness is "regressing", the forecast already used the physical
base rate – but the room decision (5-minute check, ``moisture_effect_next_5_min_ml``) still
used the learned rate (audit: 0.12 vs 0.03 → 168 vs 42 ml). Now the whole room follows the
base model; nothing learned is deleted, and without the regression the learned rate counts again.
"""
from __future__ import annotations

from custom_components.freshairiq import coordinator as coordinator_module
from ha_tests.test_door_delay_cooling_026504 import _rooms, _settled


async def test_regressing_learning_uses_the_base_rate_in_the_room_decision(hass, freezer, monkeypatch) -> None:
    status = {"status": "regressing"}
    monkeypatch.setattr(coordinator_module, "learning_effectiveness_summary", lambda *_a, **_k: dict(status))
    d = await _settled(hass, freezer, _rooms(flur_delay=0))
    await d.step(30, binary_sensor__flur_tuer="on")
    mem = d.mem("flur")

    async def effect(rate: float) -> tuple[float, float]:
        mem.update(learning_rate=rate, learning_samples=40)
        for model in (mem.get("opening_learning") or {}).values():
            model["samples"] = 0
        await d.step(10)
        room = d.room("flur")
        return room["moisture_effect_next_5_min_ml"], room["next_5_min_ml"]

    learned_regressing = await effect(0.12)
    base = await effect(0.03)
    assert learned_regressing == base           # regressing: the learned 0.12 is not used anywhere in the decision
    status["status"] = "improving"
    learned = await effect(0.12)
    assert abs(learned[0]) > abs(base[0])       # evidence fine again: the learned (faster) rate counts
    assert mem["learning_rate"] == 0.12          # what was learned is kept, never reset by the fallback
