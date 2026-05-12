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
- [IDE workflows](#ide-workflows) — VS Code, PyCharm, JetBrains Gateway
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

Coverage data lands in `.coverage`; an HTML report can be produced with
`uv run coverage html` (opens at `htmlcov/index.html`).

Linting + type-checking are part of the pre-commit hook, but you can run
them on demand:

```bash
uv run ruff format .
uv run ruff check . --fix
uv run ty check
```

---

## Running a development Home Assistant

HA runs inside Docker using the official `ghcr.io/home-assistant/home-assistant`
image — pinned to match the `homeassistant` version we develop against.
No custom Dockerfile, no `uv` in the container; the image ships with HA
and everything it needs. Your editor and the test suite run on the
**host** — the container is only for HA itself.

### Prerequisites

- **Docker** (Docker Desktop on macOS/Windows, or `docker.io` on Linux)
- **uv** on the host, for tests/lint/IDE integration:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Boot HA

```bash
docker compose up
```

First run pulls the HA image (~400MB). Subsequent runs start in seconds.
HA serves at <http://localhost:8123> once it's done booting (60-120s on
a fresh state, ~10s once the seed fixture is committed — see below).

`Ctrl-C` stops the stack. To remove the container:

```bash
docker compose down
```

To pull a newer HA image after bumping the tag in `docker-compose.yml`:

```bash
docker compose pull
docker compose up
```

### Layout

- The integration source is bind-mounted **read-only** into the container
  at `/config/custom_components/nl_rain_forecast/`. Edits on the host
  appear instantly inside HA — reload the integration (Settings → Devices
  & Services → ⋮ → Reload), or do a full HA restart via
  `docker compose restart homeassistant`.
- HA's config lives at `<repo>/config/` on the host. The committed seed
  state (a dev user + onboarding completed + the integration pre-added)
  is the minimum set of files under `config/.storage/` whitelisted in
  `.gitignore`; everything else (`home-assistant_v2.db`, logs, frontend
  cache, secrets) stays untracked.

### Dev credentials

The committed seed boots HA with one user:

| Username | Password |
|---|---|
| `username` | `password` |

This is a public-repo dev fixture, not a real credential. Don't reuse
it anywhere it matters.

### Generating / refreshing the seed fixture

The seed state is committed once and reused. Regenerate when:

- The pinned HA version changes (storage schemas may have migrated).
- You want a different default location / integration config.

To regenerate:

1. Stop HA and delete the existing seed:
   ```bash
   docker compose down
   rm -rf config/.storage/
   ```
2. Start HA:
   ```bash
   docker compose up
   ```
3. Walk through onboarding in the browser:
   - User: `username` / password: `password`.
   - Location: anywhere inside the NL bbox (e.g. Amsterdam 52.3676,
     4.9041 — the integration's bbox check needs NL coords).
   - Skip the integrations / "find devices" step.
4. Add the **NL Rain Forecast** integration (Settings → Devices & Services
   → Add Integration → search "NL Rain Forecast"). Use the same default
   coords; accept the 5-min update interval.
5. Stop HA: `docker compose down`.
6. The committable subset is already filtered by `.gitignore` — just
   `git status` and you'll see only the allowlisted `.storage/` files
   ready to stage. Commit them.

If you accidentally end up with non-allowlisted files staged
(unlikely but possible), check `.gitignore` and reconcile.

---

## Manual integration test in the dev HA

With the committed seed fixture, HA boots already onboarded as
`username` / `password` and with the integration pre-added at the
default coords. Just log in and verify state.

If you want to re-add the integration from scratch (e.g. to exercise
the config flow itself):

1. Remove the existing entry: Settings → Devices & Services → NL Rain
   Forecast → ⋮ → Delete.
2. **Settings → Devices & Services → Add Integration**, search for
   "NL Rain Forecast".
3. The config form should show:
   - Location name (default: `Home`)
   - Latitude / Longitude (defaults filled from your HA system config)
   - Update interval (5–60 min, default 5)
4. Submit. The config flow probes Buienradar, Buienalarm and Open-Meteo
   before creating the entry; if the probe fails you'll see an error.
5. On success you should see one **device** ("NL Rain Forecast: \<name\>")
   with three **entities**:
   - `sensor.<name>_rain_forecast_buienradar`
   - `sensor.<name>_rain_forecast_buienalarm`
   - `sensor.<name>_rain_forecast_open_meteo`

### What to check

- **Developer Tools → States** — all three entities should report a
  number (mm/h, often `0.0` if it's not raining) plus all the expected
  attributes: `forecast`, `peak_intensity`, `peak_time`,
  `total_precipitation`, `next_rain_in_minutes`, `next_dry_in_minutes`,
  `source`, `last_updated`.
- **`forecast` attribute** — should be a ~25 element list of
  `{time, value}` dicts spaced 5 minutes apart, covering ~2h. The
  Open-Meteo sensor is linearly interpolated from 15-min upstream data
  but reads at the same 5-min cadence.
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

Watch the compose log (HA runs with `--debug` via the image's default
entrypoint); you should see `DEBUG` lines from
`custom_components.nl_rain_forecast.sources.*`.

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
# /etc/hosts inside the container (`docker compose exec homeassistant bash`)
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

## IDE workflows

Your editor runs on the **host**, against the host's `.venv/`. Only HA runs
in Docker. That means no IDE-in-container plumbing — just a regular Python
project setup pointed at `.venv/bin/python`.

### One-time host setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv if missing
uv sync                                            # build .venv from uv.lock
uv run pre-commit install                          # register hooks
```

`.venv/` now contains Home Assistant and all dev tooling.

### PyCharm

1. Open the repo as a regular project (File → Open → pick the folder).
2. **Settings → Project → Python Interpreter → Add Interpreter → Existing**.
3. Point at `<repo>/.venv/bin/python`.
4. **Settings → Tools → Python Integrated Tools → Testing → Default test
   runner → pytest** (usually auto-detected from `[tool.pytest.ini_options]`).
5. Install the **Ruff** plugin from the JetBrains Marketplace for
   format-on-save. It uses the `ruff` binary in `.venv/bin/ruff` and
   respects our `pyproject.toml` config.

Run tests from the gutter ▶ icons. Right-click `tests/` → **Run 'pytest
in tests'** runs everything.

ty doesn't have a PyCharm plugin yet — run `uv run ty check` from the
terminal or rely on CI.

### VS Code

1. Open the repo.
2. The Python extension auto-detects `.venv/` and offers it as the
   interpreter (or pick it via the status bar).
3. Install the **Ruff** extension (`charliermarsh.ruff`) for
   format-on-save.

Run tests via the Testing sidebar or the ▶ gutter icons.

### Quick test debugging (any IDE)

```bash
uv run pytest tests/test_sensor.py::test_partial_failure_keeps_surviving_source_available -xvs
```

For deeper debugging, drop a `breakpoint()` and run with
`uv run pytest --no-cov -s path/to/test`. Both PyCharm's and VS Code's
Python debugger attach cleanly via the standard pytest entry point.

### Editing while HA is running in Docker

The repo is bind-mounted into the container at `/app`, so any code edit
on the host is visible inside HA immediately. Reload the integration via
Settings → Devices & Services → ⋮ → **Reload** to pick up changes, or
restart HA with `docker compose restart homeassistant`.

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
