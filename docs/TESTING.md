# Local testing guide

How to run the test suite, boot a real Home Assistant against this integration,
and verify behavior end-to-end before opening a PR or cutting a release.

## Contents

- [Running the automated test suite](#running-the-automated-test-suite)
- [Running a development Home Assistant](#running-a-development-home-assistant)
- [Manual integration test in the dev HA](#manual-integration-test-in-the-dev-ha)
- [Exercising partial-failure paths](#exercising-partial-failure-paths)
- [Verifying hassfest and HACS validation](#verifying-hassfest-and-hacs-validation)
- [Enabling debug logs](#enabling-debug-logs)
- [VS Code workflow](#vs-code-workflow)
- [Troubleshooting test harness issues](#troubleshooting-test-harness-issues)

---

## Running the automated test suite

```bash
uv run pytest                # full suite
uv run pytest -k buienradar  # single subset
uv run pytest --cov          # with coverage report
uv run pytest -x             # stop on first failure
uv run pytest -xvs path/to/test_foo.py::test_bar   # one test, verbose
```

`scripts/test` is a thin wrapper that always passes `--cov`. Coverage data
lands in `.coverage`; an HTML report can be produced with
`uv run coverage html` (opens at `htmlcov/index.html`).

Linting + type-checking are part of the pre-commit hook, but you can run
them on demand:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
# or all three:
scripts/lint
```

---

## Running a development Home Assistant

The repository ships with everything to boot a working Home Assistant
instance that loads this integration. Two ways to do it:

### Option A — devcontainer (recommended)

1. Open the repo in VS Code.
2. Reopen in container (`Dev Containers: Reopen in Container`).
3. On first open, `scripts/setup` runs and installs uv + the venv.
4. From the integrated terminal:
   ```bash
   scripts/develop
   ```
5. VS Code will surface a notification when port 8123 is ready. Open it
   to reach the HA onboarding screen.

### Option B — host machine

You need Python 3.14.2+ and the system deps Home Assistant uses
(`ffmpeg`, `libturbojpeg`, `libpcap`). On macOS:

```bash
brew install ffmpeg jpeg-turbo libpcap
curl -LsSf https://astral.sh/uv/install.sh | sh   # if not installed
scripts/setup
scripts/develop
```

HA boots at <http://localhost:8123> with the dev config at `config/` and
this integration on the Python path via `PYTHONPATH`. The `config/` dir
is `.gitignore`-d except for `configuration.yaml`, so restarting won't
pollute commits.

### First-time onboarding

The dev HA has no saved state on first launch. Walk through the standard
onboarding (create an owner account, set the home location). You only do
this once — onboarding state persists across restarts in `config/`.

---

## Manual integration test in the dev HA

Once HA is up:

1. **Settings → Devices & Services → Add Integration**, search for
   "NL Rain Forecast".
2. The config form should show:
   - Location name (default: `Home`)
   - Latitude / Longitude (defaults filled from your HA system config)
   - Update interval (5–60 min, default 5)
3. Submit. The config flow probes both Buienradar and Buienalarm before
   creating the entry; if the probe fails you'll see an error.
4. On success you should see one **device** ("NL Rain Forecast: \<name\>")
   with two **entities**:
   - `sensor.<name>_rain_forecast_buienradar`
   - `sensor.<name>_rain_forecast_buienalarm`

### What to check

- **Developer Tools → States** — both entities should report a number
  (mm/h, often `0.0` if it's not raining) plus all the expected attributes:
  `forecast`, `peak_intensity`, `peak_time`, `total_precipitation`,
  `next_rain_in_minutes`, `next_dry_in_minutes`, `source`, `last_updated`.
- **`forecast` attribute** — should be a 24-25 element list of
  `{time, value}` dicts spaced 5 minutes apart, covering ~2h.
- **`device_class`** is `precipitation_intensity`,
  **`state_class`** is `measurement`, **`unit_of_measurement`** is `mm/h`.
- **Icon** should be `mdi:weather-pouring` when state > 0, otherwise
  `mdi:weather-cloudy`.

### Forcing a refresh

To trigger a refresh without waiting for the scheduled interval:

```yaml
# Developer Tools → Actions
action: homeassistant.update_entity
target:
  entity_id:
    - sensor.home_rain_forecast_buienradar
    - sensor.home_rain_forecast_buienalarm
```

Watch the log (`scripts/develop` runs HA with `--debug`); you should see
`DEBUG` lines from `custom_components.nl_rain_forecast.api.*`.

### Reconfiguring the update interval

On the integration card, click **Configure** to open the options flow.
Changing the interval triggers a reload (via the update listener in
`__init__.py`).

### Adding a second location

Use **Add another** on the integration to create a second entry. Pick
different coordinates inside the NL bbox. You should get a second device
with its own pair of sensors. Re-adding the same coordinates should abort
with "already_configured" (the `unique_id` is derived from lat/lon
rounded to 4 decimals).

### Removing the integration

Settings → Devices & Services → … → **Delete** on the entry. Verify both
entities disappear and no warnings are logged on shutdown.

---

## Exercising partial-failure paths

The integration is designed so that one failing source doesn't take the
other down. To verify this manually:

### Block Buienradar with /etc/hosts (whole-host, blunt but effective)

```bash
# /etc/hosts on the machine running HA (or inside the devcontainer)
127.0.0.1 gpsgadget.buienradar.nl
```

Restart HA. Within one update interval:

- `sensor.<name>_rain_forecast_buienradar` should go **unavailable**
- `sensor.<name>_rain_forecast_buienalarm` should keep updating
- HA logs should show a single `WARNING` from
  `custom_components.nl_rain_forecast.coordinator` per refresh

Repeat with `cdn-secure.buienalarm.nl` for the inverse case.

To trigger the both-fail path, block both hosts; HA should mark the
integration entry as `setup_in_progress` → eventually fail, with
`UpdateFailed` in the log.

Don't forget to undo the `/etc/hosts` edit afterwards.

### Inject errors at the Python level (cleaner)

If you want to exercise these without touching networking, you can edit
one of the URL constants in a `*.py` file temporarily to a non-routable
host (e.g. `https://localhost:9/` ) and reload HA. This is faster than
`/etc/hosts` and reverts with `git checkout`.

### Test the config-flow probe failure

Same trick: point one of the URLs to a bad host before adding the
integration. The "Add Integration" submit should error out with
"One of the rain APIs could not be reached" rather than creating the
entry.

---

## Verifying hassfest and HACS validation

These run automatically in CI on every push (`.github/workflows/validate.yml`),
but you can run them locally with Docker too:

```bash
# hassfest
docker run --rm -v "${PWD}:/github/workspace" \
  ghcr.io/home-assistant/hassfest:latest

# HACS action
docker run --rm -v "${PWD}:/github/workspace" \
  -e INPUT_CATEGORY=integration \
  -e INPUT_IGNORE=brands \
  ghcr.io/hacs/action:latest
```

`hassfest` validates `manifest.json`, the translations files, the
config-flow schema, and so on. HACS validates `hacs.json` and the
repository layout.

---

## Enabling debug logs

The integration logs at multiple levels:

| Level | What you see |
|---|---|
| `DEBUG` | Every API call, parse step, slot-by-slot decisions |
| `INFO` | Integration setup/teardown, config changes |
| `WARNING` | Recoverable failures (one source down, parse fallback) |
| `ERROR` | Unrecoverable (will mark entry as failed) |

To turn on `DEBUG` in your dev HA, edit `config/configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.nl_rain_forecast: debug
```

Restart HA (or use the `logger.set_level` service to do it without a
restart).

---

## VS Code workflow

The devcontainer (and a similarly-configured host setup) gives you:

- **Run/debug tests from the gutter** — the Python extension picks up
  `pyproject.toml`'s pytest config and shows ▶ icons next to each test.
- **Coverage gutters** — install the
  `ryanluker.vscode-coverage-gutters` extension (already in the
  recommended list). After `uv run pytest --cov`, hit "Watch" in the
  status bar to see line-by-line coverage hints inline.
- **Ruff format-on-save** — already configured via
  `editor.defaultFormatter = charliermarsh.ruff`.
- **ty diagnostics** — Pylance is the default LSP; ty runs separately
  via `scripts/lint` and CI. If you want ty inline, the
  `ty-language-server` is an option but isn't required.

To debug a single test under `pytest`:

```bash
uv run pytest tests/test_sensor.py::test_partial_failure_keeps_surviving_source_available -xvs
```

For deeper debugging, set a breakpoint with `breakpoint()` and run with
`uv run pytest --no-cov -s path/to/test`. PyCharm and VS Code's Python
debugger both attach cleanly.

---

## Troubleshooting test harness issues

### "Connection refused" from `aioresponses` tests

The HTTP-mocking tests use regex URL patterns (`BUIENRADAR_PATTERN`,
`BUIENALARM_PATTERN`) because aiohttp encodes query strings, and an exact
URL match doesn't work. If you add a new test, mock with the pattern,
not the bare URL constant.

### Tests failing with "not a valid value for dictionary value @ data['step']"

Voluptuous error from a `NumberSelectorConfig`. HA rejects sub-`0.001`
step values; use `step="any"` for arbitrary precision.

### "We found a custom integration … which has not been tested by Home Assistant"

Harmless warning from `enable_custom_integrations` — `pytest-homeassistant-custom-component`
emits it for any custom integration. Ignore.

### Tests pass locally but fail in CI

The `uv.lock` is committed. CI uses `uv sync --frozen`. If your local
venv drifted, run `uv sync` (no `--frozen`) once and commit the new
lockfile if changes are intentional.

---

## Pre-flight checklist before a release

1. `uv run pytest --cov` — all green, coverage ≥ 80%.
2. `uv run ruff check .` and `uv run ruff format --check .` — clean.
3. `uv run ty check` — clean (or documented deviations in the README).
4. Local dev HA: add the integration, see both sensors update.
5. Local dev HA: trigger one-source failure with `/etc/hosts`, see
   correct unavailability behavior.
6. Local dev HA: change the update interval via options flow, see entry
   reload and the new interval kick in.
7. hassfest + HACS Docker validations pass locally.
8. Bump `version` in `custom_components/nl_rain_forecast/manifest.json`
   and `project.version` in `pyproject.toml`.
9. Tag the release: `git tag -a v0.1.0 -m "..." && git push --tags`.
