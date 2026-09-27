# FreshAirIQ 0.25.1.13

Hotfix based on 0.25.1.8.

- Adds a transient sensor recovery guard for short integration/startup outages; persistent sensor failures still surface after the grace period.
- Restores the Home Assistant dashboard viewport after closing FreshAirIQ overlays across delayed WebView/layout updates.
- Gives Freshy distinct situational animation states, including wind-sailing during ventilation, bedtime preparation, and sleeping at night.
