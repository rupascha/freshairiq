# FreshAirIQ 0.25.0.58 – Web Detail Scroll Hotfix

- Behebt das weiterhin blockierte Mausrad-Scrollen im Haupt-Detailfenster im Home-Assistant-Webbrowser.
- Wheel-Ereignisse werden gezielt im internen `.dialog-scroll`-Scrollport verarbeitet und nur dann vom Dashboard abgefangen, wenn das Detailfenster tatsächlich scrollen kann.
- Touch-/Mobile-Scrolllogik, Scrollpositionsspeicherung und alle übrigen Funktionen bleiben unverändert.
- Regressionstest für den Desktop-Web-Scrollpfad ergänzt.
