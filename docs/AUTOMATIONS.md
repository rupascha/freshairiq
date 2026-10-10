# Using FreshAirIQ in your own automations

FreshAirIQ **decides** but **never switches devices** itself. You decide what happens: a fan, an Alexa announcement, a Node-RED flow. Full guide with more examples (German): [AUTOMATIONEN.md](AUTOMATIONEN.md).

## Entities

* `sensor.<room>_action` – per room: `ventilate`, `continue_ventilating`, `close`, `wait`, `do_not_ventilate`, `ventilate_for_cooling`, `okay`, `check_sensor`, `monitor_only`. The full room result is in the attribute `freshairiq_room_payload`.
* `binary_sensor.<room>_close_recommended`, `sensor.<room>_mould_risk` (`low` … `very_high`)
* `sensor.freshairiq_status` – whole-home status (`okay`, `ventilate`, `ventilation_running`, `close_windows`, `wait`, …)

Exact entity IDs depend on room names and the language at setup: Settings → Devices & services → FreshAirIQ → room device.

The room action is what makes sense for *that room alone*; the whole-home recommendation may still say "wait" (rain soon, keep closed overnight). Announce the **house event** to people, drive room devices from the **room event**.

## Events (0.26.4.6+)

Fired on the Home Assistant event bus on **changes only**; after a restart the current state is taken over silently. Texts follow the Home Assistant language. Events stay local and are not uploaded to the diagnostics hub.

| Event | Key fields |
| --- | --- |
| `freshairiq_room_action` | `room_key`, `room_name`, `action`, `previous_action`, `message` (e.g. "Bedroom: Please close the window."), `reasons`, `humidity`, `temperature`, `surface_rh`, `potential_ml`, `recommended_duration_min`, `mould_level`, `ventilation_active`, `ventilation_measures_active` |
| `freshairiq_house_recommendation` | `kind`, `previous_kind`, `status`, `title`, `instruction`, `summary`, `message`, `room_keys`, `room_names`, `duration_min`, `estimated_removed_ml`, `reasons`, `night_strategy` |
| `freshairiq_mould_risk` | room fields plus `previous_mould_level`, `rising` |
| `freshairiq_notification` (0.26.4.9+) | every FreshAirIQ message as event – also when phone notifications are off: `type` (`ventilate`, `close`, `mould`, `complete`, `night`, `house_*` …), `room_key`, `room_name`, `title`, `message`, `speech` (ready for Alexa/TTS), `night_quiet_hours` |

```yaml
triggers:
  - trigger: event
    event_type: freshairiq_room_action
    event_data: { action: close }
actions:
  - action: notify.alexa_media_living_room
    data:
      message: "{{ trigger.event.data.message }}"
      data: { type: announce }
```

Node-RED: node `events: all`, event type `freshairiq_notification` for announcements (`msg.payload.event.speech`) or `freshairiq_room_action` for devices; data in `msg.payload.event`. Alexa announcements without phone pushes: keep FreshAirIQ phone notifications off and use `freshairiq_notification`.

Rooms with an exhaust fan get "Alternatively switch on the fan" in airing and mould messages. A running airing ("keep observing") is no longer pushed since 0.26.4.9 (still available as event `house_continue`).

Blueprints: `blueprints/automation/freshairiq/announce_room_action.yaml`, `device_follows_room_action.yaml`.

## Two contacts on one window (bottom = open, top = tilted)

FreshAirIQ detects 2-state and 3-state contacts automatically. Combine the two contacts into one three-state template sensor (`closed` / `tilted` / `open`) and assign **only that sensor** as the room's window contact:

```yaml
template:
  - sensor:
      - name: "Bedroom window"
        unique_id: bedroom_window_state
        device_class: enum
        state: >
          {% if is_state('binary_sensor.bedroom_window_bottom', 'on') %}open
          {% elif is_state('binary_sensor.bedroom_window_top', 'on') %}tilted
          {% else %}closed{% endif %}
        availability: >
          {{ states('binary_sensor.bedroom_window_bottom') not in ['unknown', 'unavailable']
             and states('binary_sensor.bedroom_window_top') not in ['unknown', 'unavailable'] }}
        attributes:
          options: "{{ ['closed', 'tilted', 'open'] }}"
```

Without YAML: **Settings → Devices & services → Helpers → Create helper → Template → Template sensor** with just the state template; FreshAirIQ then detects it as three-state at the latest on the first tilt. Step by step: [README.md](../README.md). Bottom open → **open**; only top open → **tilted**; both closed → **closed**.

## Recommendation aligned with the house decision (0.26.4.7+)

A room's **Action** sensor describes what would make physical sense for that room alone. The additional **Recommendation** sensor (`sensor.<room>_recommendation`) also respects the whole-house decision: while the house deliberately waits (better window later, pollen/fine dust, night strategy) it shows `ventilate_later` instead of `ventilate`. For announcements and fan automations this sensor is usually the better choice. The `freshairiq_room_action` event carries the same value in `house_aligned_action`.
