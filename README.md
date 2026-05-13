# NL Rain Forecast

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Lint](https://github.com/snoepkast/home-assistant-nl-rain-forecast/actions/workflows/lint.yml/badge.svg)](https://github.com/snoepkast/home-assistant-nl-rain-forecast/actions/workflows/lint.yml)
[![Tests](https://github.com/snoepkast/home-assistant-nl-rain-forecast/actions/workflows/tests.yml/badge.svg)](https://github.com/snoepkast/home-assistant-nl-rain-forecast/actions/workflows/tests.yml)

A Home Assistant custom integration that exposes Dutch per-5-minute rain
nowcasts from **Buienradar**, **Buienalarm**, and **Open-Meteo** as native
sensors with rich forecast attributes. No bundled Lovelace card —
visualization is your choice (ApexCharts, mini-graph-card, or anything
else).

## Why

This integration aims to be a clean, stable replacement for the popular
[neerslag-app integration](https://github.com/aex351/home-assistant-neerslag-app):

- No bundled frontend resources, no race conditions at dashboard render
- Three sources always active (Buienradar + Buienalarm + Open-Meteo) —
  partial failures don't take the whole integration down
- Config flow only — no YAML
- Async, typed, tested

## Installation

### HACS (custom repository)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=snoepkast&repository=home-assistant-nl-rain-forecast&category=integration)

1. Click the badge above (or manually: HACS → Integrations → ⋮ → **Custom
   repositories**, add `https://github.com/snoepkast/home-assistant-nl-rain-forecast`
   with category **Integration**).
2. Find **NL Rain Forecast** in the HACS list and install.
3. Restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → "NL Rain Forecast".

### Manual

Copy `custom_components/nl_rain_forecast/` into your HA `config/custom_components/`
directory and restart.

## Configuration

Single-step config flow:

| Field | Required | Default | Notes |
|---|---|---|---|
| Location name | yes | `Home` | Used as device + entity friendly-name prefix |
| Latitude | yes | HA's `config.latitude` | Must be inside the Netherlands bounding box (~50.5–53.7°N) |
| Longitude | yes | HA's `config.longitude` | Must be inside the Netherlands bounding box (~3.2–7.3°E) |
| Update interval | yes | 5 min | Range 5–60 minutes |

Multiple instances are supported (one device per location). The update
interval can be changed later via the **Configure** button on the integration.

## Sensors

Three sensors per configured location:

| Entity | Source | Native cadence |
|---|---|---|
| `sensor.<location>_rain_forecast_buienradar` | Buienradar nowcast (`gpsgadget.buienradar.nl`) | 5 min |
| `sensor.<location>_rain_forecast_buienalarm` | Buienalarm forecast (`cdn-secure.buienalarm.nl`) | 5 min |
| `sensor.<location>_rain_forecast_open_meteo` | Open-Meteo (`api.open-meteo.com`) | 15 min, linearly interpolated to 5 min |

### Sensor state and attributes

| Attribute | Type | Description |
|---|---|---|
| (state) | `float` | Current rainfall intensity in mm/h (first slot of the forecast) |
| `forecast` | `list[{time: ISO8601, value: float}]` | All slots, ~5-min spacing, ~2-hour window |
| `peak_intensity` | `float` | Maximum mm/h across the window |
| `peak_time` | `ISO8601 \| null` | Time of the peak, `null` when fully dry |
| `total_precipitation` | `float` | Total expected rainfall in mm over the window |
| `next_rain_in_minutes` | `int \| null` | Minutes until rain starts; `null` if currently raining or no rain expected |
| `next_dry_in_minutes` | `int \| null` | Minutes until rain stops; `null` if currently dry |
| `source` | `str` | `"buienradar"`, `"buienalarm"`, or `"open_meteo"` |
| `last_updated` | `ISO8601` | When the upstream data was fetched |

`device_class = precipitation_intensity`, `state_class = measurement`,
`unit_of_measurement = mm/h`. The icon switches between `mdi:weather-pouring`
and `mdi:weather-cloudy` based on the current state.

If one or two sources temporarily fail, only those sensors go
**unavailable**; the surviving source(s) keep updating. All three have
to fail for the integration to report itself as unavailable.

### A note on Open-Meteo

Open-Meteo is global; for the Netherlands it pipes the **KNMI Harmonie
AROME 2 km** model — the same model behind Buienradar and Buienalarm,
but accessed directly rather than via a rebroadcaster. Native cadence
is 15 minutes; we linearly interpolate between consecutive 15-min
boundary values to produce three 5-min sub-slots per gap so the sensor
aligns with the cadence of the other two. The interpolated 5-min values
are a visual alignment, not new model information.

## Visualization

See [docs/examples/](./docs/examples/) for ready-to-paste cards:

- [`apexcharts.yaml`](./docs/examples/apexcharts.yaml) — area chart of the
  per-5-minute forecast using `data_generator`
- [`mini-graph-card.yaml`](./docs/examples/mini-graph-card.yaml) — current
  intensity history
- [`markdown-card.yaml`](./docs/examples/markdown-card.yaml) — one-line
  "Het regent over X minuten"

## Troubleshooting

- **"Coordinates are outside the Netherlands"** — Buienradar and Buienalarm
  only cover the Netherlands, so the integration enforces an NL bbox even
  though Open-Meteo would technically work elsewhere. Pick a location
  inside the bbox.
- **One source `unavailable` after a while** — check logs for upstream errors;
  this integration logs at `WARNING` when an API call fails.
- **No update at startup** — the first refresh is awaited during setup; if
  *all three* sources fail the integration won't load. Re-add the entry
  once at least one upstream is back, or check connectivity.
- **Enable debug logging** for full request/parse traces:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.nl_rain_forecast: debug
  ```

## Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the dev setup and
[docs/TESTING.md](./docs/TESTING.md) for a full walk-through of testing
the integration locally (automated tests + a real HA instance). The
toolchain is uv + ruff + ty; quick start:

```bash
uv sync
uv run pytest
uv run ruff check
uv run ty check
```

> ty is in beta (still 0.0.x as of May 2026); if you hit a blocker, fall
> back to mypy locally and open an issue.

## Acknowledgements

Data is provided by [Buienradar](https://www.buienradar.nl/),
[Buienalarm](https://www.buienalarm.nl/), and [Open-Meteo](https://open-meteo.com/)
(which for the Netherlands serves [KNMI](https://www.knmi.nl/) Harmonie
AROME model output). This integration is unaffiliated with any of those
services. Credit also to
[ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint)
for the project scaffolding and to
[aex351/home-assistant-neerslag-app](https://github.com/aex351/home-assistant-neerslag-app)
for years of pioneering the dual-source approach in Home Assistant.

## License

MIT — see [LICENSE](./LICENSE).
