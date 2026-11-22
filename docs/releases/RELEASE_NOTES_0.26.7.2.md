# FreshAirIQ 0.26.7.2

Release after 0.26.7.1. The close recommendation now also works in rooms whose battery sensors report temperature and
humidity at different times (GitHub #30), the room's push says why it should close, the wind on the house map flows
closer along the house, and the weather animations move naturally without visible repetition and cost less on phones.
Forecasts, learning, sensor contracts and your settings stay as they are. No change to entity IDs, services, events or
card options; the new room fields are additive.

## Closing when further airing hardly helps – also with slow battery sensors (#30)
- With the default close strategy a running airing whose humidity target is still open closes once two new reports
  confirm that the next five minutes would remove less than the room's own threshold. Until now both readings had to
  arrive together. Many battery sensors only report a value when it changes, so the confirmation never came.
- A new humidity value next to an older temperature now counts – and so does a new temperature next to an unchanged
  humidity. Each counts once, and only when the benefit stays below the threshold even with the largest error the older
  reading could cause. Repeated values, reports from before the opening, refreshes without a new measurement and readings
  after the window was closed never count.
- A sensor that keeps reporting one value is not held back only because its other value has not changed for a while.
  An unavailable sensor is handled as before.
- A clear report against it ends the series: 8 → 60 → 8 ml with a threshold of 24 ml gives no close – the last value is
  the first new confirmation. A report that could lie on either side of the threshold decides nothing.
- A report that is not clear enough is not used up: when the other value arrives a little later, the same report counts
  with the synchronous pair. A close that needed such a report is withdrawn again when its readings become too old or
  unavailable. Your temperature limit, reached goals and incoming moisture keep their priority; moisture sources, CO₂,
  cooling, the room's minimum duration and "keep drying" keep the window open as before.

## Exhaust fans shared by several rooms
- A switch-off that failed once no longer comes back as a warning: as soon as every fan it concerned is off, the room's
  "could not be switched off automatically" ends – also when another room starts the same fans later. A fan that still
  runs or cannot be reached keeps the warning; the diagnostics keep the failure.
- A room whose shared fan was started by another room's automation says which one: "Gemeinsamer Ablüfter läuft ·
  gestartet von Waschküche" (English: "Shared exhaust fan running · started by …"), in the house map and the FreshAirIQ
  card. Fans switched on by hand or by another automation keep their own text.
- In the mode "with the recommendation" a fan is not restarted only because the 120-minute repeat lock ran out while
  nothing changed in the room – that caused short runs every two hours in a laundry room. A real new demand, critical air,
  a strong new moisture source or clearly drier air start it as before; moisture-source follow-up, maximum runtime and
  external locks are unchanged.

## Fixes from the support case of 21 November
- **Exhaust fan after a sensor dropout:** a fan that FreshAirIQ stopped is not started again just because the room's
  sensor dropped out for a moment and the repeat lock ran out later with the same readings. Only a valid reading that
  shows the old demand is over – or a real new reason – allows a new start. Urgent cases, follow-up time, maximum
  runtime and shared fans work as before.
- **Push for a shared phone:** when two residents share one phone and one of them is away, the one at home now always
  gets the message – once, whatever order the profiles are in. `notify.phone` and `phone` count as the same recipient;
  a notify entity stays its own recipient. Nobody at home: no message.
- **Ventilation log dates:** "From" and "To" use the date of your Home Assistant time zone – shortly after midnight "To"
  is already the new day. A date you changed in the FreshAirIQ card stays chosen during live updates, a date you left
  untouched follows the current day, and CSV and PDF export exactly that period.
- **Ventilation log order:** on the night the clocks go back, airings are listed in the order they really happened.
- **Night weather:** on the night the clocks go back, the dry hour before the rain is no longer lost.
- **Push retries:** a phone that already got a message is not sent it again when it is named differently on a retry
  (`notify.phone` / `phone`) or after a restart. A phone whose notify service only appears a little later still gets the
  message once, even when another phone already received it – within 30 minutes of the first attempt, never later.
- **Several house maps in a storm:** a new reading (temperature, humidity, water in the air) only updates the labels and
  colours on the plan; the weather and the wind keep running without being drawn again.
- **Weather forecast:** hourly values are ordered by their real time, also in the repeated hour when summer time ends.
  Precipitation from weather entities that report inches or centimetres is converted to millimetres.
- **Reordering floors:** two floors with the same name (for example the built-in "Erdgeschoss" and one you added with
  that name) each get their own field and can be moved separately. Your floors and room assignments stay as they are.

## The push says why
- A room's close push names the actual reason in German and English: "Further airing hardly removes moisture any more –
  the humidity target is not reached yet", "Humidity target reached" only when it is, your temperature limit, outdoor air
  that no longer dries, summer warming or missing readings. Still one push per recommendation.

## Why the window is not closing yet
- Every airing room carries `close_check`, a short code for the state of the check (for example `waiting_for_report`,
  `confirming`, `confirmed`, `moisture_source`), and `close_benefit_basis` once a close is confirmed. Diagnostics keep
  this code while a room airs – no raw readings and no extra samples. While the benefit is already below the threshold but
  not confirmed, the dashboard explains which readings the confirmation still needs.

## House map – wind along the house
- Long, soft, semi-transparent wind ribbons as in 0.26.7.3, each with its own width and brightness. They come a little
  closer to the wall the wind blows against and turn aside later and softly into the flow along the sides; they pass the
  corners in wide curves and never touch or cross a wall – also while they swing.
- The air slows down and splits in front of the house, runs faster along its sides and follows the walls around the
  corners. Past the last edge on its side it glides along the house's outline and closes in calmly towards the wake behind
  the house – without wrapping around its back – and the ribbons stay in order without crossing, also while they swing. Their swing stays clear of the walls and of the next ribbon and
  calms down behind the house. Wind speed, measured gusts and direction come from your chosen weather source as before.
- Storm gusts run on the ribbons. Behind the house two of them run together until they touch and carry on as one gust with
  the wind – no gap, no double track, no flash where they meet. On narrow cards the ribbons stay in sight beside the house.
- Behind the house a weak edge ribbon may roll up for a moment: the curl peels off the ribbon, drifts with the wind and
  fades.
- U-shaped houses: no ribbon runs through a wing or cuts the wall at the end of the notch any more, also with wind straight
  into the notch.
- The animation levels decide how much moves: "Minimal" a few calm ribbons without curls, "Normal" the flow
  around the house with at most one curl, "Intense" more variation and at most two. Phones keep their ceiling (24 frames per
  second, 72 points per ribbon) also for "Intense"; hidden cards and cards out of view still pause.

## House map – weather that never repeats
- **Rain, snow, sleet and hail** are single drops, flakes and hail stones instead of a repeating tile. Each one has
  its own start, speed, size, brightness and lifetime and starts again outside the picture with new values. Snow
  drifts gently sideways. The slant follows the wind as before; the strength follows the reported amount or condition
  ("pouring" is heavier than "rainy"). Sleet and hail are shown as such.
- **Live updates no longer restart the weather.** Falling weather, clouds, fog, stars, sun rays and lightning carry on
  exactly where they are when Home Assistant sends new values.
- **Wind follows your house.** A gust turns softly before it reaches a wall, flows along the real outside walls at its
  own distance, winds around the corners – also around the inner corner of an L-shaped house – and only then returns to
  the wind direction. It never breaks off, never bends sharply and never runs through a wall, also while it swings.
  Every gust has its own path, distance, width, pace and shape. Wind direction, north and the visible wind strength stay
  as they were.
- **Storm gusts** (weather effects "full") run along the same facade instead of straight bands across the house.
- **Fog** drifts as a few soft wisps of different sizes, each on its own way. Clouds pass with the wind and come back
  from outside the picture; stars and sun rays each keep their own rhythm; rain rings appear one by one where drops
  land. Lightning comes at uneven moments – not more often and not brighter than before.
- Missing or unknown weather values never add an effect.

## Lighter on phones
- Three storm cards on one page and phones need clearly less work per second: the weather canvas only clears what was
  drawn, its resolution is capped per motion level, and the animations of one card share their frames. Lightning in the
  "full" weather effect follows the same uneven rhythm as the other modes.
- Every motion level has a fixed budget for drops and flakes, drawing resolution, points per wind ribbon and storm
  gusts. On a phone or a narrow card "Intense" keeps a lower ceiling (fewer drops, a coarser drawing, 24 instead of 30
  frames per second).
- Wind, gusts and falling weather share the card's one existing animation loop; rain and snow also move in calm air.
  The wind ribbons lie in their own layer under the plan, so moving them no longer redraws rooms, labels and shadows.
- "Off", "reduce motion" and the single effect switches (wind, weather) give a still picture of their part. A hidden
  card, a card scrolled out of view, a card covered by one of its windows and a removed card stop all animation work.
- A new reading of a room sensor no longer prepares the wind again: the ways, the flow around the house and the gusts'
  timing are kept until the house, the wind, the size of the drawing or the motion level change.

## Install from the release asset
- From this release on, HACS and the Marketplace install `freshairiq.zip` attached to the release (`hacs.json`:
  `zip_release`, `filename`). Its files are the same as before; GitHub now counts these installs and updates as downloads
  of the asset. Older releases keep installing from their source archive, so going back to an earlier version from the
  repository menu works as before.
- `Actions → Download statistics` lists per release and in total the downloads of `freshairiq.zip` (Marketplace/HACS
  installs and updates plus manual and repeated downloads), the CLEAN package separately, and marks releases installed
  from the source archive as not counted instead of zero.

## Documentation
- All READMEs are in English. `README_DE.md` keeps its address for existing links and now carries the English text,
  artwork and screenshots. German app translations and the German guides are unchanged.

## Updating
- Through HACS or the Marketplace as usual, then reload the browser or the Home Assistant app once.
- If you installed an unpublished 0.26.7.2 test build, this release is not offered automatically (same version
  number): choose "Redownload" in HACS or the Marketplace and version 0.26.7.2, or unpack `freshairiq.zip` from this
  release into `custom_components/freshairiq`, then restart Home Assistant.
