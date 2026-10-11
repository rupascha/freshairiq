# Using FreshAirIQ in your own automations

FreshAirIQ **decides**, but it **never switches devices on its own**. What happens next – a fan turning on, an Alexa announcement, a light, a Node-RED flow – is up to you. There are three building blocks for this:

| Building block | What it's for | Example |
| --- | --- | --- |
| **Entities** (sensors per room and for the whole home) | Query the current state, react to state changes | `sensor.bedroom_action` changes to `close` |
| **Events** `freshairiq_*` (0.26.4.6+) | React to a *change* and get a ready-made text right away | Alexa says "Bedroom: Please close the window." |
| **Action** `freshairiq.execute_intervention` | Deliberately run a measure that FreshAirIQ has calculated | Turn on the bathroom exhaust fan |

> The exact entity IDs depend on your room names and your Home Assistant language. You'll find them under **Settings → Devices & services → FreshAirIQ → device (room) → Entities**. The examples below use typical English IDs.

> **Language of the texts:** All texts in events and notifications (`message`, `speech`, `action_label`, `title`, …) follow the FreshAirIQ output language: your Home Assistant system language – German for German, **English for every other language**. Codes such as `action`, `kind`, `type` and `mould_level` are always the same, regardless of language. German guide: [AUTOMATIONEN.md](AUTOMATIONEN.md).

---

## 1. Entities

### Per room

| Entity (example) | States / value | Typical use |
| --- | --- | --- |
| `sensor.<room>_action` | `ventilate`, `continue_ventilating`, `close`, `wait`, `do_not_ventilate`, `ventilate_for_cooling`, `okay`, `check_sensor`, `monitor_only` | **Most important trigger** per room |
| `binary_sensor.<room>_close_recommended` | `on` / `off` | "Close the window" announcement |
| `sensor.<room>_mould_risk` | `low`, `slightly_elevated`, `elevated`, `high`, `very_high` | Warning, dehumidifier |
| `sensor.<room>_moisture_potential` | ml | "Is it worth it?" condition |
| `sensor.<room>_estimated_surface_humidity` | % | Mould condition |

The room action sensor also carries the complete room result in the attribute `freshairiq_room_payload` (reasons, forecast, readings). In templates: `{{ state_attr('sensor.bathroom_action', 'freshairiq_room_payload').recommendation_reasons }}`.

### For the whole home

| Entity | Content |
| --- | --- |
| `sensor.freshairiq_status` | Home status: `okay`, `ventilate`, `ventilation_running`, `close_windows`, `wait`, `pollen_warning`, `cooling_recommended`, `sensor_error`, `critical_mould`, … |
| `sensor.freshairiq_recommended_ventilation_duration` | Minutes |
| `sensor.freshairiq_removable_moisture` | ml |
| `binary_sensor.freshairiq_cross_ventilation` | Cross ventilation detected |

**Important:** The room action describes what makes physical sense *for that room alone*. The whole-home recommendation may still say "wait" (e.g. rain in 10 minutes, keep windows closed overnight). For announcements to the people you live with, the **house event** (section 2) is therefore usually the better source; for devices in the room (exhaust fan), use the **room event**.

---

## 2. Events (0.26.4.6+)

FreshAirIQ fires events on the Home Assistant event bus – on **changes only**. After a restart, the current state is taken over silently; old announcements are not repeated. Texts follow the FreshAirIQ output language (Home Assistant system language; English for every non-German language).

### `freshairiq_room_action` – a room's action has changed

| Field | Example | Meaning |
| --- | --- | --- |
| `room_key` | `bedroom` | Internal room key (stable) |
| `room_name` | `Bedroom` | Your room name |
| `action` / `previous_action` | `close` / `continue_ventilating` | Same codes as `sensor.<room>_action` |
| `message` | `Bedroom: Please close the window.` | **Ready-to-speak sentence for Alexa/TTS** |
| `action_label` | `Please close the window` | Just the action |
| `reasons` | `["Room humidity 64 % …"]` | Up to 4 reasons |
| `humidity`, `temperature`, `surface_rh` | `64`, `21.4`, `78` | Readings |
| `potential_ml`, `recommended_duration_min` | `120`, `9` | Benefit and duration |
| `mould_level` | `high` | Same as `sensor.<room>_mould_risk` |
| `ventilation_active` | `false` | Is the room being aired right now (window/door open)? |
| `ventilation_measures_active` | `true` | Window open **or** exhaust fan running **or** shower/recovery phase detected |
| `house_aligned_action` | `ventilate_later` | Room action aligned with the whole-home decision (0.26.4.7+, see below) |
| `floor`, `data_quality`, `entry_id`, `schema_version` | | Context |

Possible `action_label` texts in English: `Please air the room`, `Keep airing`, `Please close the window` (`Please switch off the fan` for rooms aired only by a fan), `Air for cooling`, `Please do not air`, `Wait for now`, `All good`, `Check sensor`, `Monitoring only`.

### `freshairiq_house_recommendation` – the whole-home recommendation has changed

| Field | Example |
| --- | --- |
| `kind` / `previous_kind` | `ventilate`, `wait`, `continue`, `close`, `okay`, `prepare`, `pollen_wait` (outdoor air polluted: pollen and/or fine dust, 0.26.4.7+), `sensor` |
| `status` | same as `sensor.freshairiq_status` |
| `title`, `instruction`, `summary` | Texts of the recommendation |
| `message` | `Now is a good time to ventilate. Open Living room and Bathroom` |
| `room_keys`, `room_names` | Affected rooms |
| `duration_min`, `estimated_removed_ml`, `reasons`, `night_strategy`, `severity` | Details |

### `freshairiq_mould_risk` – a room's mould risk has changed

All fields of `freshairiq_room_action`, plus `previous_mould_level` and `rising` (`true` = risk is going up). With `ventilation_measures_active` you can decide for yourself whether a warning makes sense while someone is showering.

### `freshairiq_notification` – every FreshAirIQ message as an event (0.26.4.9+)

Exactly the texts FreshAirIQ would send as a push notification to your phone – **even if phone notifications are turned off or no notify service is configured**. Ideal for Alexa announcements, Telegram groups or Node-RED. Identical messages are sent at most once per notification interval (default 90 min).

| Field | Example | Meaning |
| --- | --- | --- |
| `type` | `ventilate`, `close`, `cool`, `mould`, `sensor`, `learning`, `complete`, `night`, `house_ventilate`, `house_close`, `house_wait`, `house_continue`, … | Kind of message (`house_*` = recommendation for the whole home) |
| `room_key`, `room_name` | `bathroom`, `Bathroom` | Affected room (empty for whole-home messages) |
| `title` | `FreshAirIQ · Bathroom` | Title, same as the push |
| `message` | `Ventilate now. Alternatively switch on the fan.` | Text, same as the push |
| `speech` | `Bathroom: Ventilate now. Alternatively switch on the fan.` | **Ready-to-speak sentence for Alexa/TTS** |
| `kind`, `room_keys` | `ventilate`, `["bathroom"]` | Whole-home messages only |
| `night_quiet_hours` | `true` | Quiet hours according to your FreshAirIQ settings – you decide whether to announce anyway |
| `created_at` | ISO timestamp | |

If a room has an exhaust fan, airing and mould messages include the hint "Alternatively switch on the fan". Since 0.26.4.9, airing that is already in progress ("Ventilation running · keep monitoring") is no longer sent as a push – it doesn't ask you to do anything; it is still available as an event (`house_continue`).

> Events stay inside your local Home Assistant. They are **not** sent to the Diagnostics Hub.

Try it out: **Developer tools → Events → "Listen to events"** → enter `freshairiq_room_action` → open/close a window.

---

## 3. Examples

### Alexa announces when a window should be closed

```yaml
alias: FreshAirIQ – Alexa close window
mode: queued
triggers:
  - trigger: event
    event_type: freshairiq_room_action
    event_data:
      action: close
actions:
  - action: notify.alexa_media_living_room     # your Echo device (Alexa Media Player)
    data:
      message: "{{ trigger.event.data.message }}"
      data:
        type: announce
```

### Turn on the bathroom exhaust fan while FreshAirIQ recommends airing

```yaml
alias: FreshAirIQ – Bathroom exhaust fan
mode: restart
triggers:
  - trigger: event
    event_type: freshairiq_room_action
    event_data:
      room_key: bathroom
conditions: []
actions:
  - if: "{{ trigger.event.data.action in ['ventilate', 'continue_ventilating'] }}"
    then:
      - action: switch.turn_on
        target: { entity_id: switch.bathroom_exhaust_fan }
    else:
      - action: switch.turn_off
        target: { entity_id: switch.bathroom_exhaust_fan }
```

Alternatively, `freshairiq.execute_intervention` runs the measure FreshAirIQ has calculated for the room (e.g. a configured exhaust fan or shading):

```yaml
- action: freshairiq.execute_intervention
  data:
    room_key: bathroom
```

### Announce the whole-home recommendation to everyone (instead of a phone push)

```yaml
alias: FreshAirIQ – Announce home recommendation
triggers:
  - trigger: event
    event_type: freshairiq_house_recommendation
conditions:
  - "{{ trigger.event.data.kind in ['ventilate', 'close'] }}"
  - condition: time
    after: "08:00:00"
    before: "21:30:00"
actions:
  - action: notify.alexa_media_kitchen
    data:
      message: "{{ trigger.event.data.message }}"
      data: { type: announce }
```

### Ready-made blueprints

In the repository under `blueprints/automation/freshairiq/` (English versions end in `_en`):

* `announce_room_action_en.yaml` – **Announce room recommendation**: pick rooms from a list, choose which recommendations to announce (e.g. "Close the window") and a quiet time, then choose the output (Alexa, TTS, Telegram …).
* `device_follows_room_action_en.yaml` – **Fan follows the room recommendation**: pick a room and a device; the device runs while FreshAirIQ recommends airing, and not while the window is open.

German versions: `announce_room_action.yaml`, `device_follows_room_action.yaml`. Both language versions work identically – only the UI texts differ; the announced sentence always follows the FreshAirIQ output language.

In each blueprint you pick the room via its FreshAirIQ "Action" sensor – you don't need to know any internal room key.

Import: **Settings → Automations & scenes → Blueprints → Import blueprint** and paste the raw URL of the file on GitHub, e.g. `https://raw.githubusercontent.com/rupascha/freshairiq/main/blueprints/automation/freshairiq/announce_room_action_en.yaml`.

### Node-RED

* **Announcements:** node `events: all` with *Event Type* `freshairiq_notification`. Announcement text: `msg.payload.event.speech`; room: `msg.payload.event.room_key`; kind: `msg.payload.event.type`. This replaces your own "close the window" / "turn on the fan" flow without any pushes to your phone (just leave phone notifications in FreshAirIQ turned off).
* **Events:** node `events: all` with *Event Type* `freshairiq_room_action` (or `freshairiq_house_recommendation`). The data is in `msg.payload.event` – e.g. `msg.payload.event.message` for the announcement, `msg.payload.event.room_key` and `msg.payload.event.action` for a switch node.
* **Switching a fan:** trigger on `freshairiq_room_action` with `action` = `ventilate` (or `house_aligned_action` = `ventilate` if the whole-home decision should be taken into account), followed by `fan.turn_on`; off on `close`/`okay`.
* **States:** node `events: state` on `sensor.<room>_action`; `msg.payload` is the code (`close`, `ventilate`, …).

---

## 4. Common questions from real-world setups

### Two contacts on one window (bottom = open, top = tilted)

FreshAirIQ understands **3-state contacts** (`closed` / `tilted` / `open`) and learns tilted and open separately. Combine the two contacts with a **template helper** into one window state and assign **only that helper** as the room's window contact:

| bottom contact | top contact | helper shows |
| --- | --- | --- |
| open | any | `open` |
| closed | open | `tilted` |
| closed | closed | `closed` |

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

Without YAML: **Settings → Devices & services → Helpers → Create helper → Template → Template sensor**, paste just the state template and replace both entity IDs with yours; FreshAirIQ then recognises the sensor as a 3-state contact at the latest on the first tilt. Step by step: [README.md](../README.md).

Logic: bottom open → window **open** (when the window is turned open, both contacts open); only top open → **tilted**; both closed → **closed**. Please **don't** enable the "Passage door" option for helpers like this.

### Rooms without their own window (hallway, guest WC, utility room, storage room)

* **With an exhaust fan:** set up the room as usual, enter its volume and assign the fan under *Optional devices → Exhaust fan / mechanical ventilation*. FreshAirIQ detects airing via the running fan and learns the mechanical air exchange separately.
* **With a door contact to the hallway:** add the door contact as "window/door" and choose the sensors of the room behind it (e.g. the hallway) as the **reference air for that door** – references are set per opening.
* **The hallway itself:** it has no opening to the outside. Without door contacts it doesn't get its own airing recommendation, but its humidity still counts towards the home's moisture balance, and FreshAirIQ can show passive co-ventilation while neighbouring rooms are being aired (display only, no effect on the balance). If there are door contacts to the rooms, give each door the sensors of the respective room as its reference. If several doors are open, FreshAirIQ conservatively uses the most humid source.
* **Storage room with a freezer:** if you only want to watch it, turn off *Include in FreshAirIQ calculations* (the room stays visible but doesn't influence anything).

### Mould warning while someone is showering

Since 0.26.4.6, FreshAirIQ no longer sends mould push notifications while something in the room is already working against the humidity: window open, exhaust fan running, a shower or its recovery phase detected (set "Shower" as a moisture source for the room). If the surface humidity stays high afterwards, the warning is sent – at that point you really need to act.

## Recommendation aligned with the house decision (0.26.4.7+)

A room's **Action** sensor describes what would make physical sense for that room alone. The additional **Recommendation** sensor (`sensor.<room>_recommendation`) also takes the whole-home decision into account: while the house deliberately waits (better airing window later, pollen/fine dust, night strategy), it shows `ventilate_later` ("Airing possible · wait for now") instead of `ventilate`. For announcements and fan automations this sensor is usually the better choice. The `freshairiq_room_action` event carries the same value in the `house_aligned_action` field.
