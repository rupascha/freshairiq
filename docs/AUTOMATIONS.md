# Using FreshAirIQ in your own automations

FreshAirIQ **decides** – and does **not** switch devices on its own. Only covers and exhaust fans can be controlled by FreshAirIQ itself, if you explicitly enable it per room (see "Automatic control without a blueprint" below). Everything else – a fan turning on, an Alexa announcement, a light, a Node-RED flow – is up to you. There are three building blocks for this:

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
| `sensor.<room>_action` | `ventilate`, `continue_ventilating`, `close`, `wait`, `do_not_ventilate`, `ventilate_for_cooling`, `okay`, `check_sensor`, `monitor_only`, `ventilate_indirectly` (room without its own opening contact: air via a connected room), `open_fully` (reserved) | **Most important trigger** per room |
| `sensor.<room>_recommendation` | every action value plus `ventilate_later` and `monitor_open` (long opening is being monitored) | Effective recommendation taking the whole-home decision into account |
| `binary_sensor.<room>_close_recommended` | `on` / `off` | "Close the window" announcement |
| `binary_sensor.<room>_moisture_source_active` (0.26.5.1+) | `on` while an internal moisture source is detected (shower, bath, cooking …); attributes `source` (`shower`, `bath`, `sauna`, `cooking`, `washing_machine`, `dryer`, `ironing_station`, `laundry_drying` or empty = not identified), `confidence`, `rate_ml_min`, `generated_ml`, `started_at`, `last_ended_at`, `recovery` | bathroom fan only after showering; enabled for rooms with a configured moisture source, otherwise present but disabled |
| `binary_sensor.<room>_sun_protection_recommended` (0.26.5.1+) | `on` while covers should be closed against the sun in the "summer cooling" mode; attributes `covers_to_close`, `sunlit_covers` (windows in direct sun), `sun_soon_covers` (sun arrives within the lead time), `shaded_side_covers` (windows without sun), `sun_tracking` (sun position `sun.sun` available) | close covers when the sun shines on the window and open them when it is gone; enabled for rooms with assigned covers |
| `sensor.<room>_mould_risk` | `low`, `slightly_elevated`, `elevated`, `high`, `very_high` | Warning, dehumidifier |
| `sensor.<room>_moisture_potential` | ml | "Is it worth it?" condition |
| `sensor.<room>_estimated_surface_humidity` | % | Mould condition |

From 0.26.5.1 `…_action`, `…_recommendation`, mould risk and learning status are enum sensors (`device_class: enum` with `options`). The automation editor therefore lists the translated states (e.g. "Close") for a state trigger instead of only "any state / unavailable / unknown". The values themselves are unchanged.

The room action sensor also carries the complete room result in the attribute `freshairiq_room_payload` (reasons, forecast, readings). In templates: `{{ state_attr('sensor.bathroom_action', 'freshairiq_room_payload').recommendation_reasons }}`.

Since 0.26.5.3 the room result contains no counters that change with every calculation, so the recorder writes only on real changes: instead of the age of the readings (`frame_age_*_s`, `measurement_frame_max_age_s`) it carries the report times of the sensors (`frame_temp_reported_at`, `frame_humidity_reported_at`, `frame_reference_temp_reported_at`, `frame_reference_humidity_reported_at`, `measurement_frame_oldest_at`), `last_measurement_at` is the latest report of the room sensors, `humidity_high_since` replaces `humidity_high_duration_min`, and `moisture_source_window_min` is gone. While no moisture source is active (and no recovery is running), the detector values (`moisture_source_rate_ml_min`, `…_ah_rise_g_m3`, `…_observed_change_ml_window`, `…_generated_ml_window`) show the values of the last source; the same applies to the attributes `rate_ml_min`, `generated_ml`, `source` and `confidence` of `binary_sensor.<room>_moisture_source_active`. The sensors “Overnight moisture forecast” (50 mL steps), “Estimated moisture balance today” (10 mL steps) and “Forecast temperature change” (from a 0.2 °C change) publish in meaningful steps; calculations, the dashboard and the events keep the full values. The status sensor carries a short summary only; card and panel receive the dashboard data over the live channel.

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

**From 0.26.5.3: `category` in every event.** `action` = you are asked to do something (air, close, fan on/off), `status` = information only (keep airing, wait, ended), `warning` = a risk or a fault (mould rising, check sensor). In Node-RED one filter on `category` replaces sorting out texts such as "wait" or "keep".

### `freshairiq_room_action` – a room's action has changed

From 0.26.5.1 a published "Close" is kept for the running airing until the next five minutes beat the close threshold by at least 25 % or the window is closed. The action no longer toggles between "Continue ventilating" and "Close" every 30 seconds.

| Field | Example | Meaning |
| --- | --- | --- |
| `room_key` | `bedroom` | Internal room key (stable) |
| `room_name` | `Bedroom` | Your room name |
| `action` / `previous_action` | `close` / `continue_ventilating` | Same codes as `sensor.<room>_action` |
| `category` | `action` | `action` / `status` / `warning` (0.26.5.3+) |
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
| `category` | `action` (`ventilate`, `close`, `start`, `prepare`), `warning` (`sensor`), otherwise `status` |
| `status` | same as `sensor.freshairiq_status` |
| `title`, `instruction`, `summary` | Texts of the recommendation |
| `message` | `Now is a good time to ventilate. Open Living room and Bathroom` |
| `room_keys`, `room_names` | Affected rooms |
| `duration_min`, `estimated_removed_ml`, `reasons`, `night_strategy`, `severity` | Details |

### `freshairiq_mould_risk` – a room's mould risk has changed

All fields of `freshairiq_room_action`, plus `previous_mould_level` and `rising` (`true` = risk is going up). With `ventilation_measures_active` you can decide for yourself whether a warning makes sense while someone is showering.

From 0.26.5.3:
- `message` is about the mould risk ("Office: mould risk high · surface humidity 82 %.", when falling "… down to elevated …"). Before, it accidentally carried the room's action sentence ("Office: Please switch off the fan."); that sentence is kept as `action_message`.
- `category`: `warning` while the risk rises, otherwise `status`.
- A rise is reported at once, a fall only once the lower level has held for 10 minutes. A surface humidity hovering around a level boundary therefore no longer fires an event every 30 seconds. The sensor `sensor.<room>_mould_risk` still shows the current value.

### `freshairiq_room_recommendation` – a room's effective recommendation has changed (2026-10-16+)

Fires when `sensor.<room>_recommendation` (`house_aligned_action`) changes – also when the raw room action stays the same (example: the house waited, now air: `ventilate_later` → `ventilate`). `freshairiq_room_action` deliberately does **not** fire in that case; its behaviour is unchanged.

All fields of `freshairiq_room_action` (without `previous_action`) plus `recommendation` / `previous_recommendation` (codes as `sensor.<room>_recommendation`) and `recommendation_label`; `message` is the ready sentence for the effective recommendation.

### `freshairiq_moisture_source` – an internal moisture source starts or ends (0.26.5.1+)

Fires when FreshAirIQ detects an internal moisture source in a room (`phase: started`) and when it has ended (`phase: ended`, after about 6 quiet minutes). Fields: `room_key`, `room_name`, `floor`, `phase`, `source` (code as above or `null`), `source_label` ("Shower"), `message` ("Bathroom: Shower detected."), `confidence`, `rate_ml_min`, `generated_ml`, `started_at`, `ended_at`, `humidity`, `action`. Detection needs a few minutes of clearly rising humidity; general airing recommendations (e.g. the evening pre-airing) never fire this event.

### Which signal for what?

| Signal | Meaning | Firing / restart / cooldown | Typical use |
| --- | --- | --- | --- |
| `action` (`sensor.<room>_action`, `freshairiq_room_action`) | Room action **after** alignment with the final whole-home decision for the rooms it names (air/keep airing/close); the original room physics is then kept as `canonical_action` in the room payload | immediately on every change, no cooldown; adopted silently after a restart | control devices in the room |
| `house_aligned_action` (`sensor.<room>_recommendation`, `freshairiq_room_recommendation`) | effective recommendation incl. house waiting (`ventilate_later`) and tolerated long opening (`monitor_open`) | immediately on change, no cooldown; silent after restart | per-room announcements |
| `freshairiq_house_recommendation` | one coherent whole-home recommendation | on change of kind/rooms/instruction (0.26.5.3+: without the running countdown – "about 18 min left" no longer fires a new event); silent after restart | announcements to everyone |
| `freshairiq_notification` | exactly the push texts (information **and** calls to action, see `type`) | at most once per notification interval (default 90 min) per type/room | Telegram, Alexa |

Since 2026-10-16 the whole-home decision keeps a close recommendation it already issued while the combined 5-minute return merely wobbles around the threshold (125 % hysteresis); hard close reasons (maximum duration, cooling) still act immediately.

### `freshairiq_notification` – every FreshAirIQ message as an event (0.26.4.9+)

Exactly the texts FreshAirIQ would send as a push notification to your phone – **even if phone notifications are turned off or no notify service is configured**. Ideal for Alexa announcements, Telegram groups or Node-RED. Identical messages are sent at most once per notification interval (default 90 min).

| Field | Example | Meaning |
| --- | --- | --- |
| `type` | `ventilate`, `close`, `cool`, `mould`, `sensor`, `learning`, `complete`, `night`, `house_ventilate`, `house_close`, `house_wait`, `house_continue`, … | Kind of message (`house_*` = recommendation for the whole home) |
| `category` | `action` / `status` / `warning` | 0.26.5.3+; status messages can be switched off under Notifications → "Send status messages" |
| `reminder` | `true` | only on a reminder of a still open action (0.26.5.3+) |
| `room_key`, `room_name` | `bathroom`, `Bathroom` | Affected room (empty for whole-home messages) |
| `title` | `FreshAirIQ · Bathroom` | Title, same as the push |
| `message` | `Ventilate now. Alternatively switch on the fan.` | Text, same as the push |
| `speech` | `Bathroom: Ventilate now. Alternatively switch on the fan.` | **Ready-to-speak sentence for Alexa/TTS** |
| `kind`, `room_keys` | `ventilate`, `["bathroom"]` | Whole-home messages only |
| `night_quiet_hours` | `true` | Quiet hours according to your FreshAirIQ settings – you decide whether to announce anyway |
| `created_at` | ISO timestamp | |

From 0.26.5.3:
- Room messages follow the recommendation aligned with the whole home: no "please air" while the house deliberately waits, and no "please close" while the whole-home airing keeps the room open together with others.
- No "please close" while an openly connected room is still airing usefully (Settings → Home & rooms → Open connections).
- No "switch off the fan" while another room still needs the same fan.
- "Reminder of an open action" (5–60 min, off by default) repeats an action not done yet, prefixed with "Reminder:".

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
* `fan_after_moisture_source_en.yaml` – **Fan after a moisture source (e.g. showering)** (0.26.5.1+): pick the "Moisture source active" sensor and a device; the device starts as soon as a shower or similar is detected and keeps running for a follow-up time after it ends (default 10 min), at most the maximum runtime (default 60 min). Optionally only for selected sources. The evening pre-airing never switches the fan.
* `covers_follow_sun_protection_en.yaml` – **Covers against the sun (summer cooling)** (0.26.5.1+): pick the "Sun protection recommended" sensor (optionally only some covers). In the "summer cooling" mode the covers of windows the sun is about to shine on close – by default 15 minutes ahead – when a warm day is expected (forecast high from 25 °C, a room above its comfort target or already warm) and the sky is not densely clouded; they open again once the sun has left these windows – not merely because the room cooled down. Optional: keep them closed after sunset. Requires the window direction and the cover assignment in the room setup; without a direction or without `sun.sun` only warmth and brightness decide.

German versions: `announce_room_action.yaml`, `device_follows_room_action.yaml`, `fan_after_moisture_source.yaml`, `covers_follow_sun_protection.yaml`. Both language versions work identically – only the UI texts differ; the announced sentence always follows the FreshAirIQ output language.

In each blueprint you pick the room via its FreshAirIQ "Action" sensor – you don't need to know any internal room key.

**Choose the basis (from 0.26.5.1):** both blueprints ask what they should follow:

* **House decision (as shown on the card)** – follows `freshairiq_room_recommendation`. When several rooms are aired together it stays at "Keep airing" until the house should close, so announcements never come earlier than on the card. Default of the announce blueprint.
* **Room only (this room alone)** – follows `freshairiq_room_action`, i.e. what would be right for this room alone; reacts earlier. Default of the fan blueprint (previous behaviour).

Home Assistant does not update blueprints you already imported: re-import the blueprint (same URL, overwrite) and pick the basis in the automation.

Import: **Settings → Automations & scenes → Blueprints → Import blueprint** and paste the raw URL of the file on GitHub, e.g. `https://raw.githubusercontent.com/rupascha/freshairiq/main/blueprints/automation/freshairiq/announce_room_action_en.yaml`.

### Automatic control without a blueprint (0.26.5.1+)

Covers and exhaust fans need no blueprint: under **Settings → Devices & services → FreshAirIQ → edit room** FreshAirIQ can control them itself. Everything is **off** by default; do not use a blueprint for the same device at the same time.

* **Per window/door** (opening settings, where you also assign the covers): **"Open the cover when this window/door opens"** – when it is opened (also tilted) the cover goes fully up, when it is closed it returns to its previous position. If someone moved the cover in between, it is left as it is. The position is remembered across a Home Assistant restart.
* **Passage door** ("passage door" enabled): the cover never closes while the contact does not report "closed" (not even when its state is unknown). In rooms with automatic cover control, a close started by anyone else (button, scene, automation) is stopped and the cover is opened again – so nobody gets locked out on the balcony or terrace.
* **Per room, section "Automatic control":**
  * **"Close covers against the sun automatically"** – like the blueprint "Covers against the sun": only in the "summer cooling" mode, only windows in direct sun; covers open again once the sun is gone – but only covers FreshAirIQ closed itself. If the window is open and "Open the cover …" is enabled, the cover closes once the window is closed.
  * **"Switch the exhaust fan automatically"** – *after a moisture source* (like the blueprint "Fan after a moisture source", with follow-up time) or *following the recommendation* (on while airing is recommended and no window is open), each with a maximum runtime. FreshAirIQ only switches off what it switched on itself; if you switch the fan off, it stays off until the reason has ended.

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

A room's **Action** sensor describes what would make physical sense for that room alone. The additional **Recommendation** sensor (`sensor.<room>_recommendation`) also takes the whole-home decision into account: while the house deliberately waits (better airing window later, pollen/fine dust, night strategy), it shows `ventilate_later` ("Airing possible · wait for now") instead of `ventilate`. While the house tolerates a long, thermally stable opening ("long opening is being monitored") it shows `monitor_open` instead of `close` for those rooms. For announcements and fan automations this sensor is usually the better choice. The `freshairiq_room_action` event carries the same value in the `house_aligned_action` field; when only this value changes, `freshairiq_room_recommendation` fires.
