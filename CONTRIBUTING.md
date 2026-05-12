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

For a step-by-step walk-through of running tests and exercising the
integration in a real Home Assistant instance, see
[docs/TESTING.md](./docs/TESTING.md).

## Common commands

| Command | What it does |
|---|---|
| `uv run pytest` | Run the full test suite |
| `uv run pytest --cov` | … with coverage report |
| `uv run ruff format .` | Format |
| `uv run ruff check . --fix` | Lint (auto-fix what's safe) |
| `uv run ty check` | Type-check |
| `docker compose up` | Boot a dev Home Assistant with this integration loaded |

## Docker (for running HA)

HA runs in Docker via the official `ghcr.io/home-assistant/home-assistant`
image (`docker-compose.yml` — no custom Dockerfile). The integration
source is bind-mounted into the container; HA's config is seeded with a
committed `username` / `password` user + the integration pre-added, so
`docker compose up` boots straight to a working instance. Your editor
and the test suite run on the host against `.venv/`. See
[docs/TESTING.md](./docs/TESTING.md) for the full walk-through.

## Branching and PRs

1. Branch off `main`.
2. Keep changes focused — one concern per PR.
3. Update tests for any behavior change.
4. Before opening the PR:
   ```bash
   uv run ruff format --check .
   uv run ruff check .
   uv run ty check
   uv run pytest
   ```
5. CI must pass: `lint.yml`, `tests.yml`, hassfest, and HACS validation.

## Cutting a release

Releases are auto-published by `.github/workflows/release.yml` whenever a
`v*` tag is pushed. HACS only recognises *releases* (not bare tags), so
this is what users will see as the installable version.

1. Bump the version in **both**:
   - `custom_components/nl_rain_forecast/manifest.json` (`"version"`)
   - `pyproject.toml` (`[project] version`)
   The workflow refuses to publish if they disagree with the tag.
2. Commit on `main` (e.g. `chore: bump version to v0.2.0`).
3. Tag and push:
   ```bash
   git tag -a v0.2.0 -m "v0.2.0"
   git push origin v0.2.0
   ```
4. The release workflow produces a GitHub release with auto-generated
   notes (PRs merged since the previous tag).

Pre-release tags (`-alpha`, `-beta`, `-rc`, or trailing `a1`/`b1`/etc.)
are marked as pre-releases automatically and won't be picked up as the
default install in HACS.

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
