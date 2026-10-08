# FreshAirIQ 0.26.2.11

Runtime hotfix for three confirmed v0.26.2.10 regressions:
- fixes the `NameError: include_back is not defined` in the room-goal/contact-reference flow;
- removes the duplicate Back helper text;
- routes every Rooms trigger through one persistent ShadowRoot click delegate instead of listeners recreated after each render.
