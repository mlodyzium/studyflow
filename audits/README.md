# Quality reports

- [Initial user-journey audit](2026-09-30-user-journeys.md): reproduced defects and investigation scope.
- [Repair verification](2026-09-30-repairs.md): fixes and verification evidence.
- `browser-smoke.mjs`: Chromium scenarios with controlled API responses.
- `auth-language-smoke.mjs`: login and registration language switching with controlled API responses.
- `user_journeys_probe.py`: historical audit reproductions; maintained regression tests are in `tests/test_user_journeys.py`.

Test totals in dated reports describe the suite at that point in time. They are not a live coverage metric or a security certification. Polish test inputs intentionally verify the supported Polish interface and language interpretation.
