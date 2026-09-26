# FreshAirIQ 0.4.1

## Setup error fixed

Home Assistant returned device identifier records containing three values, while
FreshAirIQ 0.4.0 assumed exactly two and failed with:

`ValueError: too many values to unpack (expected 2, got 3)`

0.4.1 parses registry identifiers defensively and only reads the first two fields
(domain and stable identifier value). Additional Home Assistant registry metadata
is ignored.

All persistent FreshAirIQ learning/history data remains untouched.
