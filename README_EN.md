# FreshAirIQ

[Deutsch](README.md) · **English**

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
> **Beta diagnostics:** pseudonymized automatic diagnostics are set to **“Daily at night”** by default. Coarse **device/browser context** is enabled by default so Android, iOS, browser, and rendering problems can be distinguished. Both options can be changed or disabled at any time under **FreshAirIQ → Energy & Data → Diagnostics sharing**. Direct identifiers such as resident names, entity IDs, IP addresses, email addresses, and URLs are removed or pseudonymized before transmission.

---

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

---

# For beta testers

We are looking for real-world variety rather than the largest possible install count: apartments and houses, basements, different sensor manufacturers, small and large setups, Android, iOS, and browsers. Feedback about **initial setup, clarity of recommendations, forecast behavior, learning progress, mobile views, and unusual building situations** is particularly valuable.

### Diagnostics & privacy during beta

FreshAirIQ keeps a limited technical diagnostic history locally. During the public beta, automatic pseudonymized transmission is enabled **daily at night** by default and distributed over time per installation. Coarse device/browser context is enabled by default. Both can be disabled at any time.

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
