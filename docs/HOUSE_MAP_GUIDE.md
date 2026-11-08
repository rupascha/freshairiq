# House map (optional)

The house map shows your FreshAirIQ rooms on a freely shaped floor plan: which room needs action and why,
how far windows and doors are open, where the wind comes from and which air paths **presumably** follow.
It is an additional card – the existing dashboard, entities, recommendations, notifications and
automations stay unchanged.

![House map – cross ventilation through the house (demo render)](images/house_map_cross_ventilation_en.png)

## Set-up in four steps

1. **Add the card:** edit dashboard → add card → "FreshAirIQ house map" (YAML: `type: custom:freshairiq-house-card`).
   Or choose **House map (floor plan)** under "Dashboard style" of an existing FreshAirIQ card – it then shows
   the floor plan instead of the dashboard.
2. **Look at the proposal:** on first use FreshAirIQ proposes a plan from your rooms, floors, room dimensions
   or volumes, shared door contacts, open connections and window orientations. It is marked
   "Automatic proposal – not saved yet".
3. **Adjust it:** "Edit floor plan" (administrators only): move, resize and rotate rooms, set corners,
   drag windows onto the right wall.
4. **Check north and save:** with nothing selected, answer "Which compass direction does the top of your plan face?" –
   drag the "N" arrow of the compass rose or enter the angle (0° = top is north, 90° = top is east, 180° = top is south,
   270° = top is west; 345° means "the top faces roughly north-northwest"). The rooms are not rotated. Tick "North
   direction checked" only once the direction was checked against a site plan, a map or a compass – only then does the
   map assign sun and wind to individual walls.

You can skip all of this: the unsaved proposal already shows temperature, humidity, recommendations and
opening states.

## What the proposal knows – and what it does not

Home Assistant knows room names and floors, but **no** wall coordinates or window areas. Every room shows
its origin: *calculated from the setup* (length × width), *estimated* (area from volume ÷ height, 2.5 m if
unknown, assumed square), *schematic* (no size known, not to scale) or *confirmed by you*. The proposal
never changes room volumes or the room setup and is not re-arranged after a restart, weather change or
update. "Propose again" first shows how many rooms would change; "Add missing rooms" only adds new rooms.

## Editor

![Editor: wall length, angles, 90° and locks](images/house_map_editor_90_locks_en.png)

- **Quick:** drag a room to move it, top-right handle to resize, "Rotate 90°" (in the room's properties after tapping it:
  turns it about its centre, anticlockwise, windows and doors turn with it; four times = as before, ↶ undoes it), rectangle/L/U templates,
  drag openings along their wall.
- **Precision:** drag corners, the dot in the middle of a wall inserts a corner, select a corner + Del/✕
  removes it, numeric coordinates, grid 0.05–0.5 m.
- Undo/redo (also Ctrl+Z/Ctrl+Y), zoom, fit, pinch zoom, arrow keys move the selected room.
- Openings: kind (window, door, roof window, passage, vent), mechanism (turn-tilt, casement, tilt only,
  sliding …), width, assigned contacts. Connections per room (open passage, door, stairs, shaft, duct).
- **View (0.26.6.0):** the floor plan fills the whole card. **☰ Menu** lies on the plan at the bottom right with the layers
  (action, temperature, humidity, CO₂, air paths, quality), details (recommendation, weather, wind and figures), floors,
  guests, notes about the drawing (proposal, estimated room sizes, north, schematic wind streams, air-path model) and
  support & diagnostics and editing. Notes that need a tap (another floor, live connection disrupted, auto focus paused)
  lie on the plan at the top left. Exterior walls thick, shared interior walls thin; windows, doors and passages with their
  own symbols; connections without a drawn opening get a marker on the wall.
- **Air stream (0.26.6.0):** air coming in through an open window moves only through connections – the drawn door or passage
  between two rooms, else the middle of the shared wall of a connection – never through a wall; without such a place the
  stream ends. At the other end it streams out of the open window again (also out of a second open window of the same
  room when no air path is known).
- **Floors (UI hotfix 0.26.6.0):** the other floors as buttons in a bar at the bottom edge of the card, below the plan (never over it); no "All floors" – for several floors add the card several times, each with `floor: ground_floor` / `floor: upper_floor` (floor id, level or name); each card keeps its own choice; a floor that needs an action (air now, close, critical) pulses gently, with reduced motion it keeps a static mark.
- **Menu and support:** the menu is a window over the plan; "Support & diagnostics" opens a window with the same functions as the FreshAirIQ card (diagnostics with required description, export, feedback).
- **Touch editing:** tap a room, wall, door or window; a finger on something not chosen moves the view, two fingers zoom, only the chosen room can be dragged. Tap a wall → enter its length in m, choose the corner that stays, apply; "Lock length" keeps it. Doors: hinge left/right and opening direction. A "door"/"open passage" connection can be drawn as a door/passage on the shared wall.
- **Editing window (0.26.6.1):** the editor opens full screen in its own window – however narrow the card is on the
  dashboard. The drawing is the centre and keeps its size: on wide screens and in landscape the properties stand beside
  it at a fixed width, on a tablet in portrait and on a phone in a fixed share below it (scrolling on their own). At the
  top: floor, **Quick | Precision** (Quick: move and resize whole rooms; Precision: corners, wall lengths and angles),
  **+ Room**, **Window**, **Door**, **Passage** and **More** (grid, snap to 90°, fit rooms together, propose again,
  export/import, help). Undo/redo and zoom/fit sit in the bottom corners of the drawing, save and discard under the
  properties. A short hint over the drawing says what the chosen object or tool does ("Tap an outside wall to place a
  window."), otherwise the next sensible step; with nothing chosen the properties show the steps floor → rooms →
  position/shape → windows/doors → contacts → save with ticks. "+ Room": choose the room, its shape as a picture
  (rectangle, L, U, own shape = a rectangle in Precision mode), add. Properties by object: room (area, add window, rotate,
  edit corners, floor; corners as numbers and connections in sections), wall (length, corner that stays, lock, angles),
  window/door (kind, width, hinge, contact; position and mechanism in sections). On a phone "Drawing only" gives the
  drawing the whole height, the selection stays and "Edit" brings its properties back. "Fit" stays on until you zoom or
  move the view. Colours follow the Home Assistant theme; if its contrast is too low the editor uses a checked light or
  dark palette.
- **One wall at a time, angles and locks (editor):** a wall length changes that wall only – the chosen corner stays,
  the other one moves along the wall and the next wall takes up the change. The opposite wall keeps its length; a room
  does not have to stay a rectangle. Neighbouring rooms are never dragged along – if the wall would grow into a
  neighbour, the editor refuses and says why.
  - **Lock wall after wall:** "Lock length" keeps a length, "Lock angle at corner …" keeps an angle. Locked walls and
    angles are carried along by later edits (the locked stretch moves as a whole). If that is impossible **nothing**
    changes and the message names the wall or corner and a way out ("unlock it or keep the other corner in place").
    Free geometry stays free.
  - **90°:** the wall panel shows the angles at both corners (inner corners of L and U rooms as 270°) and a
    "Corner … to 90°" button each – only that corner is squared, never all rooms. "Snap to 90°" in the toolbar makes a
    dragged corner near 90° (±6°) snap to an exact right angle; the grid still applies.
- **Fit rooms together (editor):** measure rooms one by one, push them roughly together (to within about 35 cm) and
  tap "Fit rooms together". Facing walls are found (also 3.92 m next to 3.98 m); every room only moves as a whole –
  nothing is scaled or bent, locked dimensions win. A **preview** comes first (dashed rooms, shared walls in green, notes
  on different lengths, locked corners or overlaps); it is saved only after "Apply", undo/redo work. Afterwards the
  shared walls are interior walls (drawn once), doors on them link both rooms, windows stay on the outside wall.

  ![Fit rooms together – preview](images/house_map_join_preview_en.png)

- **Door swings in the editor only:** the editor shows a door's swing as a fine arc (to set hinge and direction).
  The house map shows the door leaf with its state and no arc; an invisible arc takes no label space.
- **Sun position:** the sun stands where `sun.sun` reports it (azimuth and elevation, turned by the plan's north) and
  moves along during the day – redrawn in 2° steps, not on every Home Assistant state change. Without a checked north
  the map only shows even daylight from above – no sun and no rays on a side that might be wrong.
- **Window with another room's contact:** a window is drawn where it is – also when its contact belongs to another
  room's setup (e.g. a guest WC window that airs the hall). The editor offers every contact for a window, those of other
  rooms marked "(airs …)". The map shows the sensor's real state; the hall's ventilation decision stays as it is. A
  contact used by two rooms only becomes a door in the proposal when it is set up as a door or is a door sensor in
  Home Assistant.
- **Floor names:** editor and map show readable names (ground floor, upper floor, basement, attic …); internal ids
  stay unchanged.
- **Room look (0.26.6.0, sixth build):** the room surface shows the state (calm/cool = all well, muted amber = wait, green/cyan/orange = act, coral with hatch = critical, a soft inner rim when an action is needed); the name on the surface, the state as a dark capsule, temperature/humidity in large rooms. The editor reports windows on an interior wall and moves them to the outside wall with one tap.
- **Labels and weather (seventh build):** labels always stay inside the real room outline (also L/U shapes); rooms too small show a state dot. Top right the outdoor weather or own sensors (`weather_sensors: sensor.a, sensor.b`).
- **Atmosphere (eighth build):** no grid – a sky that follows the weather (`sun.sun` for day/twilight/night – at night a deep night sky, rooms in dim cool light, stars by cloud cover; sun, clouds, fog, rain and snow slanted with the wind, thunder flash – only from Home Assistant data, never over the house). Rooms show their climate at rest: warm/cool glow, mist when humid (↑ while rising), dry texture, mould risk speckles along the walls, steam at a moisture source, a turning fan. While airing, fresh air reaches in at open windows (shorter when tilted) and fine particles travel with the streams; after closing it fades out. Labels keep readings before the state word and avoid door swings; small rooms show a short name ("WC"). A modelled picture, not a flow simulation.
- **Wind and air (ninth build):** a modelled wind field on a canvas layer: fine glowing threads with fading trails, broad clear air masses, deflection at the outside walls, occasional eddies behind the corners, gusts as events (measured gust when known). Through open windows the air flows into the house and on through doors to the other window; after closing it fades out. Top left: removable moisture of the whole house and the airing time (tap for the explanation). Labels keep readings and full names (two rows if needed).
- **Tenth build:** top left shows exactly the FreshAirIQ card's "removable now" and its recommended airing time (while airing: removed so far and time left). The wind's character follows the weather – light and warm in the sun, calm when cloudy, denser in rain, epic in a storm.
- **Keyboard in the editor:** tap a room, then the arrow keys (Shift = ten grid steps); undo with Ctrl/⌘+Z. A dragged room
  snaps onto a neighbour's wall line (guide line) and cannot be dropped onto another room.
- **Place openings** (bar above the drawing, also without a template): "Tap a window", "Tap an interior door",
  "Tap a passage", then tap a wall. Interior doors and passages belong on a wall between two rooms (otherwise
  "no interior wall"); the air paths read them as the link of both rooms. A door counts as open by its contact,
  a passage is always open.
  The whole width must lie on a shared wall stretch (walls up to 5 cm apart; a shared corner is not enough); the
  editor centres the opening on that stretch and shortens its width if needed. If it no longer fits later, it shows
  "counts as an outside opening".
- **Width:** drag the two round handles at the ends of a selected opening (it stays centred, inside its wall,
  at least 0.3 m, on the grid) or use "−"/"+" (5 cm each) or the "Width (m)" field.
- Problems are shown at the room ("walls cross", "overlaps another room" …); an invalid plan is not saved.
- If someone else saved in the meantime nothing is overwritten: export your draft and reload.
- Export/import as JSON.

## Floor plan template (upload a picture and tap the rooms)

Per floor you can put a picture of your plan behind the drawing (architect plan, estate agent plan, scan or photo):

1. **Upload picture** (editor → "Floor plan template"): PNG, JPEG or WebP. **PDF is not supported** – save the page
   as a picture first or take a straight photo of the plan. The picture is downscaled in the browser (longest side
   2000 pixels) and stays local in Home Assistant.
2. **Scale:** tap two points of a distance with a known length (e.g. a dimensioned wall) and enter it in metres.
   Without a scale no room is taken over.
3. **North** (optional): tap two points along the plan's north arrow – first its tail, then its tip.
4. **Tap a room:** the area enclosed by walls is detected, outlined and measured. The best matching FreshAirIQ rooms
   are suggested (compared with length × width or volume ÷ height from the room set-up); one tap assigns. A room
   that was already drawn is replaced; its windows move to the wall facing the same direction and keep their contacts.
5. **Tap a window:** tap on a wall to place a window there.

If the area is "not closed" or runs into the next room, an open door or passage connects them: raise **Close gaps**
or draw a **Separator** across the passage. Furniture, labels and dimension lines usually do not disturb; strong
shadows, oblique photos or very thin wall lines may. Detection runs entirely in the browser. There is deliberately
no fully automatic recognition of all rooms, windows and doors.

## Layers, openings, wind

Wind is drawn as soft, translucent wave ribbons that turn at walls and enter through confirmed open windows.
The waves keep flowing without a restart – also when data changes or the map is redrawn; stronger wind makes
them faster. With the device's "reduce motion" or the animation switched off they stand still.

Layers: action · temperature · humidity · CO₂ · air paths · quality. Each room's action comes from exactly the
same data as the dashboard, notifications and automation events; colour is never the only information.

| Opening shown as | Meaning |
|---|---|
| tilted / fully open | only with a proven three-state contact |
| open – kind unknown | ordinary window contact (open/closed) |
| contact open – confirmation running | this contact's configured opening delay is still running |

Wind comes from the weather entity (degrees or compass text; km/h, m/s, mph, knots). The arrow shows where
the wind comes **from**; without a direction, with stale data or calm air no arrow is drawn. Air paths are an
**estimate** – no measurement, no air speed – at the model level *connections only*, *wind estimate* (needs a
checked north or configured window orientations) or *wind + opening type*. Tap a path for its basis,
assumptions and unknowns. Single-sided airing is shown as exchange at the window; nothing is claimed through
closed doors, stairs or ceilings; a reference sensor in a neighbouring room does not prove an air path.

## Floors

The other floors are buttons in a bar below the plan; a floor that needs an action pulses gently. There is no
"All floors" overview any more – for several floors add the card several times (`floor: ground_floor`,
`floor: upper_floor` …). `auto_focus`: `off`,
`hint` (default, shows "Action on another floor"), `auto` (moves to a floor with a **new** action; a manual
choice is kept for `manual_lock_min` minutes, at most one automatic switch per minute).

```yaml
type: custom:freshairiq-house-card
auto_focus: hint          # off | hint | auto
layer: action             # action | temperature | humidity | co2 | airflow | quality
manual_lock_min: 10
animation: true
# 0.26.7.0+ – all of it also in the card editor; without these the card looks as before
room_info: [name, temperature, absolute_humidity, action]   # name | temperature | humidity | absolute_humidity | action | co2 | mould
room_overrides: { bad: [temperature, mould] }               # own choice per room (room key)
rooms_button: true        # "Rooms" button next to the menu
floors_visible: [ground_floor, upper_floor]                 # floors shown (id, level or name; never none)
default_floor: ground_floor                                 # this floor whenever the card is opened
weather_effects: dynamic  # off | subtle | dynamic (as before) | full
weather_entity: weather.home                                # optional, else FreshAirIQ's weather entity
weather_info: [compact, overview, hourly, daily, wind, sun, datetime]   # + compass (compass rose on the plan)
weather_details: [temperature, condition, humidity]        # values in the weather window (empty = none; not given = all)
weather_chip: [temperature, condition, wind]               # top right: temperature | condition | humidity | wind | rain | apparent | pressure | sun | datetime
animation_level: auto     # off | minimal | normal | intense | auto (device, card size, reduced motion)
animation_parts: [wind, weather, light, ambient]           # what may move
layout: auto              # auto | focus | info
design: freshairiq        # freshairiq (default) | ha (Home Assistant theme) | custom (own colours)
design_accent: "#7a3cff"  # custom only: accent colour of the buttons
design_background: "#ffffff"   # custom only: card background (#rrggbb or transparent)
design_dialog: "#f4f1e8"  # custom only: window background
design_text: auto         # custom only: auto | light | dark
design_border: 2          # custom only: border width 0–6 px
design_radius: 12         # custom only: corner radius 0–32 px
```

### Design & colours (0.26.7.0+)

In the card editor under **"Design & colours"**. Without it the card keeps the FreshAirIQ design (blue, as before).
- **Use the Home Assistant theme** (`design: ha`): the card's frame and windows take the background, text, accent and
  border colour, border width and corner radius of the dashboard's theme; switching between a light and a dark theme
  is taken over at once. A transparent (glass) theme stays transparent; its windows get an opaque background.
- **Custom** (`design: custom`): own accent, card and window colour, text colour, border width and corner radius.
- Plan, weather, light, wind and the state colours of the rooms (ventilate, wait, close, critical) are the same in every
  design. The weather window keeps its sky on purpose.
- Every colour is checked against its background (text at least 4.5:1, buttons 3:1). A choice or theme that misses
  this is replaced by a readable colour automatically; the editor says so.
- Limit: with the glass effect the card does not know the dashboard's background – text directly on the transparent
  card (outside the plan and the windows) cannot be checked. The settings apply to this card only.

### Room information (0.26.7.0+)

`room_info` sets what each room shows on the plan – any combination (e.g. only `temperature`, or `temperature`,
`absolute_humidity` and `action`). Without it the label is as before (name, state, readings of the chosen layer). Another
layer chosen in the menu (temperature, humidity, CO₂, quality) still shows its reading. `room_overrides` gives single rooms
their own choice. Where a small room cannot hold everything the readings go first, then the name is shortened – door
leaves and open sashes stay free. Hidden values are always in the room details (tap the room).

### Rooms overview, floors, moisture by room

- **"Rooms"** (`rooms_button: true`): every room of the shown floors with temperature, relative and absolute humidity,
  recommendation, mould risk and removable moisture. A tap opens the room details, ⌖ jumps to the room on the plan
  (its floor, a short highlight). Live values update the open window in place.
- **Floors:** `floors_visible` hides floors in this card only – the calculation and the saved plan stay unchanged, the
  auto focus never switches to a hidden floor, at least one floor always stays. `default_floor` shows that floor
  whenever the card is opened; every card on every dashboard keeps its own settings.
- **The millilitres at the top left:** below the explanation the split by room – exactly the values FreshAirIQ publishes
  per room (no second calculation): without airing the realistic amount for the recommended time, while airing the amount
  removed so far and the time left. The total is the FreshAirIQ card's; if the rounded room values add up differently,
  the difference is shown.

### Weather world (0.26.7.0+)

`weather_effects`: `off` (no weather effects), `subtle` (calmer: no flash, no rays, slower precipitation), `dynamic`
(default, the look until now) and `full`. "Fully animated" joins house and weather:

- **Light of the real sun** (`sun.sun`): colour and strength follow the sun's elevation – warm and golden in the morning
  and evening, clear and white at noon; clouds dim it. The sky changes steplessly with the elevation between day,
  twilight and night. The house's shadow falls away from the sun and grows longer when it stands low – only with a
  confirmed north, otherwise without a direction; no hard shadow under a closed cloud deck.
- **Wind:** clouds and rain follow the measured wind direction (where it comes from, turned into the house's
  orientation); with strong wind and storm (Bft 8+ or gusts from 72 km/h) gusts sweep across the garden. The air streams
  in the house stay the modelled airing – a different quantity than the outdoor wind.
- **Rain, thunderstorm, snow, fog, frost:** rain slanted by the wind, with moderate and heavy rain rings on the ground and
  a darker sky; the strength is graded only with an amount from the hourly forecast, otherwise by the reported condition.
  Thunderstorms with a rare, soft brightening (no measured strike; no flashing with reduced motion). Fog takes the
  distance away, frost gives a cool light (an illustration, not a measurement).
- **Night:** a dark sky, stars when it is clear, the moon only with a moon-phase entity (`sensor.moon_phase`) – an
  illustration of its phase in the corner, never an invented position.

Effects stay outside the rooms; rooms, windows, contact states and recommendations come first. A card outside the visible
area or on a hidden page pauses its animations; small cards draw fewer effects; reduced motion and `animation: false`
keep everything still, every weather value stays available.

**Weather overview:** a tap on the weather at the top right (or "Weather" in the menu) opens the overview in the house
map's sky: condition and temperature, feels like, humidity, pressure (converted to hPa), chance of rain, date and time,
the sun's day arc with sunrise, sunset and its position, the next hours as a temperature curve with rain bars, the next
days as temperature ranges and the wind as a compass rose (direction, km/h, gusts, Beaufort). Forecasts come through Home
Assistant (`weather/subscribe_forecast`), shared by every house map and only while something shows them – no extra
weather API. A missing value shows "–"; without a forecast or with the weather source unavailable the current picture
stays.

**Weather source and wind:** with an own `weather_entity`, wind speed, gusts and direction come from exactly that entity –
for the overview, the compass rose, the drift of clouds and rain and the wind streams. If it lacks a single value (or is
unavailable), only that value falls back to FreshAirIQ's wind; the compass rose then says "Wind partly from FreshAirIQ".
Without an own entity FreshAirIQ's wind is used as before. Directions are accepted as degrees or compass points (N, NNE,
NW, SW … in English and German) and turned into the plan's north. Date, time, the sun's arc and forecast times follow
Home Assistant's time zone (with the profile setting "local time" the browser's). Forecast subscriptions are shared per
Home Assistant connection; after a connection change they are subscribed anew.

### Weather, rooms, menu and animation (0.26.7.0, second round)

**Top right** shows what `weather_chip` chooses (in that order); without a choice outdoor temperature and humidity as
before (or the older `weather_sensors`), an empty choice shows nothing there. A `weather_chip` choice wins over
`weather_sensors`. A tap on the display always opens the weather window, also with `weather_info: [compact]`. A narrow card shows the first entries. A tap opens the **weather window**: the
present weather large (a drawn weather symbol, temperature, condition, high/low, date and time), the values as tiles, the sun
with day length and elevation, the wind with gusts and a Beaufort scale, the next hours and days. Which values appear is set
by `weather_details` – a value switched off never comes back by itself; with the condition switched off no symbol appears
either. What the source lacks is simply left out.

**Rooms:** every room card is one button (name, floor, recommendation in its state colour, temperature, relative and absolute
humidity, mould risk, removable moisture). A tap opens the room's details and shows its floor behind; "Show on the plan" is in
the room's details. **Room details** (also by tapping the room on the plan): the room is clearly outlined on the plan, the rest
steps back, windows and doors stay visible; plus everything the FreshAirIQ card knows about the room – the reason with every
cause, climate, wall and mould, moisture and forecast, air exchange, moisture source, fan, learning, windows and doors, the room
model, extra sensors.

**Menu** (bottom right): information (the house's decision and key figures, "More about the decision" with every background
view of the FreshAirIQ card – water in the house air, airing threshold, night forecast, pollen, IQ decision, last airing –,
"Learning & forecast quality" with "FreshAirIQ is currently learning", the learning areas and the passive formula
comparison, moisture overview, weather, rooms), control & modes (guests, the animation level – what the plan shows is the card setting "Start layer"), tools (edit the floor plan, airing log
as PDF/CSV, support) and notes.

**Wind and animation:** no small white strokes any more – calm, slower wind ribbons, each with its own lane, length, wave, pace
and brightness; light wind shows a few faint ribbons, a storm more and livelier ones. `animation_level` *auto* chooses by
device: reduced motion → off, a phone or small card → minimal, otherwise normal. Only *auto* calms down after 2 minutes without a touch
and stands still after 10 minutes until it is touched again; a level chosen explicitly (minimal, normal, intense) stays while the card is
visible. *Intense* shows more wind ribbons in three layers, a stronger swing, livelier clouds, rays and precipitation – still no white strokes, 30 frames a second. Hidden, scrolled-away or covered cards pause; all
house maps share one animation loop (12/20/30 frames per second by level instead of 60).

**Layout:** `auto` uses the free space beside the plan on wide cards (where the plan is limited by the screen height) for
weather and the house's state; `focus` shows the plan only; `info` always with the weather and status column. The column
stands beside the plan, never over it; the plan's coordinates stay unchanged.

### 0.26.7.0 UI hotfix

- **One continuous surface:** no solid blue bars above and below the plan. Sky, weather and wind ribbons run on under the controls (no
  second animation loop). The sky and the moving weather (clouds, rain, snow, fog, stars, flash, gusts, rain rings) lie in their own
  layer under the plan that the browser only moves or fades instead of painting the drawing again – rain and storm stay smooth on
  large screens too; floors, rooms, menu, moisture and weather displays sit over it semi-transparently and never
  cover rooms, windows or doors. With the animation off the background stays still; at *minimal* (phones, saving energy) the wind stays around the house too and only the still sky continues under the bars.
- **Back in every window:** "‹ Back" at the top left goes back exactly one level (menu → learning → back → menu; rooms → room →
  back → rooms), the scroll position is kept; "Close" closes everything; Escape acts like Back. Opened right from the plan there is
  no made-up menu step.
- **Sun arc:** the sun always lies on the drawn curve; the day from sunrise to sunset (noon at the top), at night a flat arc below
  the horizon until the next sunrise. With Home Assistant's location the card computes the day's sunrise and sunset itself (checked
  against astral, the library of HA's sun integration), otherwise from `sun.sun`. Polar day and polar night are named.
- **The weather display at the top right** reacts to mouse and touch again (a decorative layer caught the clicks).
- **Absolute humidity** (g/m³) as a choice at the top right (`weather_chip: abs_humidity`) and in the weather window
  (`weather_details: abs_humidity`): without an own weather entity FreshAirIQ's outdoor value, otherwise from the chosen entity's
  temperature and humidity with the integration's own formula; invalid values are left out. Existing choices stay.
- **Menu:** "View on the plan" is gone; the card setting "Start layer" decides the view.

## What the map deliberately does not do (yet)

No flow computation (no deflection around corners, no facade vortices, no obstacles); wall exposure is a
classification and air paths are lines between openings and room centres. Tilted vs. fully open differs in symbol
and class only, not in angle, sash direction, effective area or flow rate. The proposal only produces rectangular
rooms in two simple arrangements – draw real L/U shapes, the outline and split levels in the editor. Floor auto
focus defaults to hint only (`auto_focus: auto` switches automatically). No PDF template (pictures only), no fully automatic room recognition.

## Privacy and limits

The plan is stored locally in Home Assistant (`.storage/freshairiq.house_layout.<entry>`), is **not** sent to
the diagnostics hub and is not part of the diagnostics export. A plan template (picture) is kept separately in `.storage/freshairiq.house_underlay.<entry>`, also local only and not part of diagnostics; it is shown in the editor only. Deleting the integration deletes both files. No cloud, no map services; without internet or
wind data the map stays fully usable. Saving is for administrators only; Home Assistant areas, floors and
devices are only read. No CFD, no measured air volumes, obstacles are not considered. Example plan without real
data: [examples/house_map_demo.json](examples/house_map_demo.json).
