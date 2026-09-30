# User-journey audit — September 30, 2026

**Historical findings.** The defects below were addressed in the subsequent [repair report](2026-09-30-repairs.md).

## Method

The existing 67 backend tests passed. Eight additional scenarios failed against an isolated PostgreSQL database. Model responses were controlled so application behavior could be tested independently of model variability. Production user data was not changed.

## Reproduced defects

1. Renaming a subject through AI to an existing name returned HTTP 500 instead of a conflict message.
2. Moving a calendar task did not update the associated plan day's date.
3. Sending `title: null` when editing a plan day caused HTTP 500 instead of input validation.
4. The standalone plan generator ignored a request to start tomorrow.
5. Continuing a deleted conversation failed because the browser retained its proposal ID.
6. Moving the first plan day did not update the plan's overall start date.
7. A combined request to distribute time evenly and add exercises changed the durations but ignored the content request.
8. Planning a session for tomorrow incorrectly added its duration to today's completed-study statistics.

## Additional code-review findings

- A closed assistant could process a late response and start speech playback.
- Some data-loading failures were hidden from the user.
- Regeneration saved another material immediately; a failed generation could leave an empty topic.
- Bulk selection did not respect the API limit of 1000 IDs.
- Generated five-minute plan days could not be edited because the editor required at least ten minutes.

## Reproduction

The original probes are preserved in `user_journeys_probe.py`. Maintained regressions are now part of `tests/test_user_journeys.py`.

```sh
docker compose --profile test run --rm --build tests
```

Use an isolated test database: the test fixture recreates tables.

## Scope limits

This audit combined code review, logs, and API tests. It did not test every browser, physical microphone, or possible natural-language request. It was not a comprehensive penetration test.
