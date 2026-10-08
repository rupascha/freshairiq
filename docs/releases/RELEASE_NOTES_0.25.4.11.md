# FreshAirIQ 0.25.4.11

Hotfix for the release performance gate only. The benchmarked production hot paths are byte-identical to v0.25.4.9/v0.25.4.10. The performance gate control workload was increased 10x and rounds from 7 to 11 because the former control interval was sub-millisecond and produced false regressions under scheduler jitter. Warning/failure thresholds remain unchanged. The baseline was recalibrated against the accepted v0.25.4.9 production code with the corrected measurement method.
