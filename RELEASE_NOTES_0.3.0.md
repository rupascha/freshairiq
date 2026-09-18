# FreshAirIQ 0.3.0 – Brand & clean-domain release

FreshAirIQ is the new project identity of the V14.2.1 Community Engine.

## Branding
- Project name: **FreshAirIQ**
- Developer: **rupascha**
- Tagline: **Intelligent lüften. Gesund wohnen. Energie sparen.**
- Clean Home Assistant domain: `freshairiq`
- Central device: **FreshAirIQ**
- Device manufacturer/developer: **rupascha**

## Migration
An existing pre-FreshAirIQ `ventilation_assistant` config entry is detected during setup. FreshAirIQ can import its room/outdoor configuration with one confirmation. If learning storage exists, it is copied to FreshAirIQ on first startup.

Because the integration domain changes, entity IDs created by the new integration use the `freshairiq` prefix. Dashboards and automations should be moved to the new entities after parallel validation.

## Existing features retained
- central hub + one HA device per room
- multiple ventilation contacts per room
- ANY/ALL ventilation paths
- direct room volume or length × width × height
- indirect ventilation through neighbouring rooms
- adaptive five-minute yield and close logic
- surface humidity / mould-risk estimate
- persistent per-room learning
- German and English setup/options UI
