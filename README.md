# FreshAirIQ

[Deutsch](README_DE.md) · **English**

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/freshairiq-branding-official.png" alt="FreshAirIQ – Intelligent Home Climate" width="720">
</p>

<p align="center"><strong>Your home can tell you when ventilation is actually worthwhile.</strong></p>

FreshAirIQ is a Home Assistant integration for intelligent, explainable ventilation decisions. Instead of merely displaying relative humidity, it combines **absolute humidity, the amount of water in room air, indoor/outdoor climate, room volume, window states, weather, temperature trends, presence, and learned building behavior** into a concrete recommendation.

**Wait → Ventilate → Keep ventilating → Close.** For individual rooms, floors, or the whole home.

> [!IMPORTANT]
> ## 🧪 Public beta
> FreshAirIQ is currently in public beta. We are looking for Home Assistant households with different buildings, sensors, platforms, and ventilation habits. Feedback and errors can be submitted directly from FreshAirIQ to the diagnostics hub.
>
> **Beta diagnostics:** pseudonymized automatic diagnostics are sent **only after your explicit consent**. After the update the dashboard card asks admins once: “Share diagnostics?” – until then nothing is uploaded automatically. You can change the decision at any time under Settings → Privacy & diagnostics or Devices & services → FreshAirIQ → Configure. Once you agree, the default cadence is **“Daily at night”** and coarse **device/browser context** is included so Android, iOS, browser and rendering problems can be told apart; both can be changed.

---

## Two dashboard styles – with Freshy by your side

The FreshAirIQ Community Dashboard card includes **two dashboard views**. In the dashboard configuration you can switch at any time between **Classic** and **FreshAirIQ IQ**. You can keep the familiar classic presentation or use the more visual FreshAirIQ interface – both views remain available.

> [!NOTE]
> **Experimental FreshAirIQ IQ / Freshy dashboard:** This dashboard is still in an experimental phase. Its graphics, animations, layout, and visual presentation may change from version to version while the design is being refined. The **Classic** dashboard remains available as the more established view.

FreshAirIQ also has its own mascot: **Freshy**. Freshy keeps an eye on your home's climate and makes the current situation easier to understand at a glance. During ventilation Freshy rides the wind, shortly before night Freshy gets ready for bed with a sleeping cap, and at night Freshy sleeps. Other states react to the current situation in your home as well.

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/00-freshy-dashboard.jpeg" alt="FreshAirIQ dashboard with Freshy" width="520">
</p>

## FreshAirIQ in action

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/01-house-ventilation.jpeg" alt="FreshAirIQ whole-home ventilation with live forecast" width="520">
</p>

### One decision instead of a wall of measurements

FreshAirIQ continuously evaluates the current situation and presents one primary recommendation. During ventilation it shows **how much moisture has already been removed**, the expected additional benefit of the next few minutes, the temperature trend, and when the useful endpoint is reached.

The reasoning remains visible: thresholds, expected net effect, learned patterns, data quality, and forecast confidence are not hidden behind an opaque “AI says …”.

---

## What makes FreshAirIQ different

| Feature | What FreshAirIQ does with it |
| --- | --- |
| **Absolute humidity & water balance** | Converts humidity to g/m³ and, together with room volume, into an understandable amount of water vapor in ml. |
| **Dynamic ventilation recommendations** | Evaluates the expected real benefit instead of relying only on a fixed RH threshold. |
| **Room, floor & whole-home ventilation** | Determines whether rooms should be handled individually or as a coordinated group. |
| **Live balance** | Tracks actual humidity and temperature changes during ventilation. |
| **Short-term forecast** | Simulates 5–120 minutes and estimates the efficient endpoint within the forecast window. |
| **Night strategy** | Forecasts conditions through the night using occupancy, outdoor air, and learned night patterns. |
| **Mould IQ** | Provides a conservative surface-RH indicator and highlights rooms that deserve attention. |
| **Energy & cost context** | Estimates temperature loss and reheating energy for the configured heating system. |
| **Presence & guests** | Adapts moisture forecasts to expected occupancy and overnight guests. |
| **Additional sensors** | Can use CO₂, VOC/TVOC, PM2.5, pollen, illuminance, wind, and other contextual data. |
| **Explainable decisions** | Shows reasons, data quality, learning maturity, and forecast confidence. |
| **Persistent learning** | Learns real room behavior and routines from suitable observations without silently changing user thresholds. |

---

## Every room has its own physics

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/02-room-overview.jpeg" alt="FreshAirIQ room overview" width="520">
</p>

FreshAirIQ does not treat rooms as identical boxes. Volume, sensor readings, windows, orientation, learned air exchange, and previous ventilation results are tracked per room. A small guest WC can therefore behave differently from a large open-plan living area or basement room.

The room view combines room climate, absolute humidity, water content, mould indicator, and learning status. Rooms can also be configured as observation-only rooms without influencing the whole-home decision.

---

# FreshAirIQ Intelligence 2.0

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/03-intelligence-overview.jpeg" alt="FreshAirIQ Intelligence 2.0 learning overview" width="520">
</p>

FreshAirIQ deliberately separates **experience maturity** from **forecast quality**. A large number of measurements does not automatically make a model good. FreshAirIQ therefore counts independent days, ventilation sessions, and robust outcome comparisons, while separately showing how closely forecasts matched reality.

### Four learning areas

**Your home** learns room physics, moisture buffering, and whole-home ventilation strategies. **Forecasts & learning** corrects live forecasts, compares predictions with real outcomes, and evaluates alternative shadow models in parallel. **Your habits** learns daily routines, adopted strategies, and personal context. **Long-term learning** collects night and seasonal experience slowly across genuinely different days and seasons.

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/05-learning-home.jpeg" alt="FreshAirIQ learning room physics and moisture buffering" width="430">
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/06-learning-forecast.jpeg" alt="FreshAirIQ forecasts and shadow learning" width="430">
</p>

### Learning has to become measurably better

FreshAirIQ validates its learned forecast model against real outcomes and a frozen baseline model. Model generations can be replayed under comparable conditions. MAE, directional accuracy, independent ventilation sessions, different days, and statistical uncertainty remain visible.

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/04-model-quality.jpeg" alt="FreshAirIQ model quality and diagnostics" width="520">
</p>

The learning system is not allowed to simply claim improvement: meaningful learning effectiveness requires multiple independent ventilation sessions on different days and conservative evidence rules.

---

## Making moisture tangible

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/07-water-balance.jpeg" alt="Water in home air by room" width="520">
</p>

Relative humidity depends on temperature and can be difficult to interpret by itself. FreshAirIQ additionally calculates **absolute humidity** and the resulting **amount of water in room air**. This makes it easier to understand where moisture is located and how much can realistically be removed through ventilation.

Throughout the FreshAirIQ interface: **minus = moisture removed**, **plus = moisture added**.

---

## Mould IQ – an early indicator, not a laboratory diagnosis

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/08-mould-iq.jpeg" alt="FreshAirIQ Mould IQ" width="520">
</p>

FreshAirIQ estimates a conservative surface RH from the available room climate and highlights noteworthy rooms. This can help identify persistently problematic climate conditions. Without an actual surface-temperature measurement at a specific building component, FreshAirIQ **cannot determine or rule out real mould growth**.

---

## More features

FreshAirIQ supports freely configurable floors and rooms, multiple window/door contacts per room, opening delays, window orientation and wind context, alternative outdoor/reference air, pollen veto, CO₂ context, VOC/TVOC, PM2.5, and illuminance. Residents can be linked to `person.*`/`device_tracker.*`; children or other people without trackers remain supported. A quick guest mode immediately adjusts short-term and night forecasts.

For energy estimates, heat pumps, gas, heating oil, district heating, or direct electric heating can be configured with the relevant parameters. Optional actuators do **not** automatically imply autonomous control: FreshAirIQ remains recommendation-oriented by default and only performs explicitly enabled, clearly defined interventions.

---

# Install the beta

## Your own automations (Node-RED, Alexa, fans)

FreshAirIQ never switches devices itself – but you can react to every recommendation: via the room entities (e.g. `sensor.bedroom_action`) or via the events `freshairiq_room_action`, `freshairiq_house_recommendation` and `freshairiq_mould_risk`, which carry a ready-to-speak sentence. Examples, two blueprints and tips for tilt contacts and rooms without windows: **[docs/AUTOMATIONS.md](docs/AUTOMATIONS.md)** (German, with more detail: [docs/AUTOMATIONEN.md](docs/AUTOMATIONEN.md)).

## Requirements

- Home Assistant **2026.8.0 or newer**
- HACS for the recommended installation method
- For calculated rooms: temperature, relative humidity, room volume, and at least one window/door contact
- Outdoor reference: a local `weather.*` entity **or** outdoor temperature + outdoor relative humidity

## Installation via HACS

1. Open **HACS → Custom repositories**.
2. Add `https://github.com/rupascha/freshairiq` as an **Integration** repository.
3. Install **FreshAirIQ**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → FreshAirIQ**.
6. Rooms, sensors, and additional options can then be configured through **Devices & services** or the FreshAirIQ settings icon.

> FreshAirIQ can initially be added without a completed room setup. If required climate data is missing, calculations are withheld instead of inventing values.

## Manual installation

Copy the complete `custom_components/freshairiq` folder to `/config/custom_components/freshairiq`, restart Home Assistant, then add FreshAirIQ under **Settings → Devices & services**.

## Window contacts: 2-state, 3-state – or two contacts on one window

FreshAirIQ detects the kind of window contact **automatically**:

- **2-state** (`binary_sensor`, open/closed) – read as a normal window.
- **3-state** (closed / tilted / open, e.g. a Homematic handle sensor) – FreshAirIQ learns *tilted* and *open* separately.

**You have two 2-state contacts on one window** (bottom = window turned open, top = window tilted)? Combine them in Home Assistant with a **template helper** into one 3-state sensor and give FreshAirIQ only that helper as the window contact.

| bottom contact | top contact | helper shows |
| --- | --- | --- |
| open | any | `open` |
| closed | open | `tilted` |
| closed | closed | `closed` |

**Option A – in the UI (no YAML)**

1. **Settings → Devices & services → Helpers → Create helper → Template → Template sensor**.
2. Name, e.g. `Bedroom window`.
3. Paste into **State template** and replace both entity IDs with yours:

   ```jinja
   {% if is_state('binary_sensor.bedroom_window_bottom', 'on') %}open
   {% elif is_state('binary_sensor.bedroom_window_top', 'on') %}tilted
   {% else %}closed{% endif %}
   ```

4. Leave the unit empty and save.

**Option B – YAML (`configuration.yaml`)** – with availability and an options list, so FreshAirIQ recognises the sensor as 3-state right away:

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

Then restart Home Assistant or use **Developer tools → YAML → Template entities**.

**In FreshAirIQ:** edit the room and select **only the new helper** (`sensor.bedroom_window`) as the window/door contact – not the two single contacts as well, otherwise the window counts twice. With option B FreshAirIQ detects the three states immediately, with option A at the latest when the window is tilted for the first time.

---

# For beta testers

We are looking for real-world variety rather than the largest possible install count: apartments and houses, basements, different sensor manufacturers, small and large setups, Android, iOS, and browsers. Feedback about **initial setup, clarity of recommendations, forecast behavior, learning progress, mobile views, and unusual building situations** is particularly valuable.

### Diagnostics & privacy during beta

FreshAirIQ keeps a limited technical diagnostic history locally. Since 0.26.3 it is uploaded automatically to the FreshAirIQ diagnostics server (`diagnostics.freshairiq.com`, HTTPS) **only with your consent**; undecided or “No” means nothing is sent automatically. After consent the chosen cadence applies (default: nightly, spread per installation between 02:00 and 03:59). A support package you send yourself counts as consent for that single upload.

Direct identifiers are removed or pseudonymized before upload. Diagnostics are intended for technical analysis, forecast/learning validation, and compatibility issues—not advertising or profiling. Free-text feedback is transmitted only when you explicitly submit it.

---

# Technical principles

FreshAirIQ is vendor-independent and works with Home Assistant entity semantics. Canonical ventilation physics is based on psychrometric quantities and remains separated from optional context sensors. Sensor latency, data quality, and measurement freshness are considered; unsuitable measurements should not become trusted learning evidence.

The project includes a Continuous Quality System with pure-logic tests, frontend/contract tests, release hygiene, and GitHub/HACS release gates. A release ZIP is only generated after the intended quality gates pass.

### Local quality checks

```bash
python tools/quality_gate.py --profile local
python tools/build_release.py
```

### Updates

For HACS installations, published GitHub releases are used as the update source. The release tag and `custom_components/freshairiq/manifest.json` must use the same version. Learning and history data are stored separately in Home Assistant storage and remain intact during normal updates.

### Removal

First remove the FreshAirIQ integration entry under **Settings → Devices & services**, then restart Home Assistant. For manual installations, `/config/custom_components/freshairiq` can then be removed.

---

## ☕ Support FreshAirIQ

FreshAirIQ is an independent open-source project. If you like FreshAirIQ and would like to support continued development voluntarily, you can buy me a coffee:

**[☕ Buy me a coffee – FreshAirIQ](https://buymeacoffee.com/freshairiq)**

Feedback, bug reports, and beta testing are equally valuable and very welcome.

---

## Project status

**FreshAirIQ · Public Beta**

FreshAirIQ is under active development. Forecasts and recommendations are decision aids for indoor climate and do not replace professional building, mould, health, or safety assessment.

Developed by **rupascha** for Home Assistant.
