# FreshAirIQ 0.25.2.31

Hotfix for notification delivery. The coordinator now invokes the notification pipeline independently of its existing `changed` flag, preventing state persistence work from short-circuiting push processing. Includes the unchanged dark-surface contrast correction from 0.25.2.30.
