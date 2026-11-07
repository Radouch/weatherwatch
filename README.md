# WeatherWatch

Telegram bot that fetches current conditions and a short forecast for a
handful of places from [Open-Meteo](https://open-meteo.com) and pushes them
to a configured chat on a daily schedule (plus on demand via `/weather`).
Runs as a long-polling systemd service, developed here and deployed on an
Odroid.

## Configuration

- `config.json` - places (geocoded via Open-Meteo, matched client-side by
  `country`/`admin1`), schedule times (local time), weather variables, units.
  **Never put secrets here.**
- `.env` (gitignored, template in `.env.example`) - `TELEGRAM_TOKEN`,
  `CHAT_ID`. Must sit in the service's working directory.
- Runtime state (Telegram update offset) lives in
  `WEATHERWATCH_STATE_DIR` - defaults to `./state`; the systemd unit uses
  `/var/lib/weatherwatch` via `StateDirectory=`.

## Install & run

```bash
python -m venv .venv
.venv/bin/pip install -e .          # dependencies from pyproject.toml
.venv/bin/weatherwatch              # or: python weatherwatch.py
```

`pip install -r requirements.txt` still works (it just contains `-e .`).

## Deploy (Odroid)

1. Sync the project to `/home/radek/weatherwatch`
2. Place `.env` there (never through git)
3. `.venv/bin/pip install -e .`
4. `sudo systemctl daemon-reload && sudo systemctl restart weatherwatch`
5. Watch `journalctl -u weatherwatch -f`

## Versioning

- The **single source of truth** for the version is `version` in
  `pyproject.toml`. The running service logs it at startup.
- To release: bump `version`, commit, then tag:
  ```bash
  git tag -a v0.1.0 -m "First packaged release"
  ```
  (push tags to a remote later with `git push --tags`)
- Distributions build with `python -m build` into `dist/` (gitignored).

## Development

- Lint: `ruff check .` (config in `pyproject.toml`).
- The `telegram` and `scheduler` package names may clash if this venv ever
  also installs PyPI's `telegram` / `schedule`-ecosystem packages - for this
  private venv that's fine; renaming to a `weatherwatch.*` namespace is the
  next step if dependencies ever require it.
