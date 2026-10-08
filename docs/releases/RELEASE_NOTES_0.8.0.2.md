# FreshAirIQ v0.8.0.2 – Migration / Setup Hotfix

## Behoben
- `NameError: CONF_ROOMS is not defined` beim Setup nach der v0.8-Migration.
- Fehlender Import des Home-Assistant-Moduls `config_entries`, das für
  `async_add_subentry`, `async_update_subentry` und `async_remove_subentry`
  benötigt wird.
- Doppelter `MappingProxyType`-Import bereinigt.
- Frontend-Cache-Buster auf 0.8.0.2 angehoben.

Der Fix verändert keine Lernwerte und keine gespeicherten Raumdaten.
