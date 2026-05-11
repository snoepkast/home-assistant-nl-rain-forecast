# Contributing

Contributions are welcome — bug reports, fixes, documentation improvements.
This is a personal project, but it tries to hold itself to public-quality
standards.

## Local development setup

The toolchain is [uv](https://docs.astral.sh/uv/) + [ruff](https://docs.astral.sh/ruff/)
+ [ty](https://docs.astral.sh/ty/). All three are managed via the
`[dependency-groups]` in `pyproject.toml`; no system pip needed.

```bash
# 1. Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sync the venv from uv.lock
uv sync

# 3. Install pre-commit hooks
uv run pre-commit install
```

Or run the bundled bootstrap:

```bash
scripts/setup
```

For a step-by-step walk-through of running tests and exercising the
integration in a real Home Assistant instance, see
[docs/TESTING.md](./docs/TESTING.md).

## Common commands

| Command | What it does |
|---|---|
| `uv run pytest` | Run the full test suite |
| `uv run pytest --cov` | … with coverage report |
| `uv run ruff check` | Lint |
| `uv run ruff format` | Format |
| `uv run ty check` | Type-check |
| `scripts/lint` | format + lint --fix + ty in one go |
| `scripts/test` | pytest with coverage |
| `scripts/develop` | Boot a dev Home Assistant with this integration loaded |

## Devcontainer

`.devcontainer.json` is set up for VS Code Dev Containers. It includes
Python 3.14, uv, and the apt deps Home Assistant needs (ffmpeg, libturbojpeg,
libpcap). On first open, `scripts/setup` runs automatically.

## Branching and PRs

1. Branch off `main`.
2. Keep changes focused — one concern per PR.
3. Update tests for any behavior change.
4. Run `scripts/lint` and `uv run pytest` before opening the PR.
5. CI must pass: `lint.yml`, `tests.yml`, hassfest, and HACS validation.

## Type-checking caveat

`ty` is still in beta (0.0.x). If you hit a false positive or an unsupported
language feature:

1. Try a `# ty: ignore[<rule>]` comment on the offending line.
2. If that's not enough, open an issue describing the case — we'll either
   work around it or fall back to mypy for the whole project.

## Reporting bugs

Use [Issues](https://github.com/snoepkast/home-assistant-nl-rain-forecast/issues).
Include:

- Home Assistant version
- Integration version
- Relevant log lines (set `custom_components.nl_rain_forecast` to `debug`)
- A minimal reproduction (e.g. coordinates that consistently misbehave)

## License

By contributing you agree your contributions are licensed under the
[MIT License](./LICENSE).
