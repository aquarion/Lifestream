# Lifestream

Lifestream is a collection of Python scripts that aggregate personal data from various online services into a unified MySQL database. It powers sites like [NicholasAvenell.com](http://nicholasavenell.com) and enables building unified activity feeds and data archives.

## Features

- **Multi-source data collection**: Import from Last.fm, Flickr, Foursquare, GitHub, Mastodon, Steam, Bluesky, and many more
- **Flexible scheduling**: APScheduler with Redis persistence for reliable job execution
- **Webserver**: FastAPI/uvicorn webserver behind a reverse proxy, with CORS support — serves the OAuth callback catcher and future data APIs
- **Failure notifications**: Email and Slack alerts when jobs fail
- **Caching**: Redis-based caching to reduce API calls

## Quick Start

```bash
# Clone repository
git clone https://github.com/aquarion/Lifestream.git
cd Lifestream

# Install dependencies
poetry install

# Configure the application
cp config.example.ini config.ini
# Edit config.ini with your database and API credentials

# Initialize the database
mysql -u user -p database < schema.sql

# Test a single import
poetry run python supervisor.py --run lastfm
```

## Configuration

Copy `config.example.ini` to `config.ini` and configure:

- **[database]**: MySQL connection details
- **[redis]**: Redis connection for caching and scheduler persistence
- **[webserver]**: host/port to bind, CORS allowed_origins, and the public domain used for OAuth redirect URLs
- **[schedules]**: Job schedules using cron expressions
- **[notifications]**: Email and Slack alerting (optional)
- **Service-specific sections**: API keys and credentials for each service

## Running Imports

### Supervisor (Recommended)

The supervisor runs all import jobs (APScheduler + Redis persistence) and
the webserver (OAuth callback catcher, future data APIs) in one process:

```bash
# List configured jobs
poetry run python supervisor.py --list

# Check next run times
poetry run python supervisor.py --status

# Run a single job immediately
poetry run python supervisor.py --run lastfm

# Start the supervisor (scheduler + webserver)
poetry run python supervisor.py
```

For production, install the systemd service:

```bash
sudo cp docs/lifestream-supervisor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lifestream-supervisor
```

### Manual

New-style importers (in `src/lifestream/importers/`) can be run directly via
the `lifestream-import` console script:

```bash
poetry run lifestream-import --list
poetry run lifestream-import lastfm
```

Remaining legacy scripts under `imports/` (not yet migrated to the new-style
importer classes) are still run directly, e.g. `poetry run python imports/wow.py`.
See `docs/crontab.example` for cron-based scheduling of either style using
`bin/run_import.sh` (legacy; superseded by the supervisor above).

## Project Structure

```
supervisor.py         # Main supervisor daemon (scheduler + webserver)
config.ini            # Configuration (not in repo)
schema.sql            # Database schema

src/lifestream/
  cli.py              # `lifestream-import` console script
  core/               # Core library
    config.py         # Config/credentials/project-root helpers
    cache.py          # Redis caching utilities
    db.py             # Database connection and EntryStore
    jobs.py           # Job execution functions
    logging.py        # Logging setup
    notifications.py  # Email/Slack notification sending
    oauth_utils.py    # OAuth token file helpers
    steam_api.py      # Steam Web API client
  importers/          # New-style importer classes (BaseImporter subclasses)

imports/              # Remaining legacy import scripts, not yet migrated

tests/                # Test suite
docs/                 # Systemd service, crontab examples
bin/                  # Shell helper scripts
contrib/              # Additional tools
```

## Testing

```bash
# Run all tests
poetry run pytest tests/

# Run with verbosity
poetry run pytest tests/ -v
```

## License

MIT
