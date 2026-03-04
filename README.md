# Lifestream

Lifestream is a collection of Python scripts that aggregate personal data from various online services into a unified MySQL database. It powers sites like [NicholasAvenell.com](http://nicholasavenell.com) and enables building unified activity feeds and data archives.

## Features

- **Multi-source data collection**: Import from Last.fm, Flickr, Foursquare, GitHub, Mastodon, Steam, Bluesky, and many more
- **Flexible scheduling**: APScheduler with Redis persistence for reliable job execution
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
poetry run python scheduler.py --run lastfm
```

## Configuration

Copy `config.example.ini` to `config.ini` and configure:

- **[database]**: MySQL connection details
- **[redis]**: Redis connection for caching and scheduler persistence
- **[schedules]**: Job schedules using cron expressions
- **[notifications]**: Email and Slack alerting (optional)
- **Service-specific sections**: API keys and credentials for each service

## Running Imports

### Scheduler (Recommended)

The scheduler manages all import jobs with APScheduler and Redis persistence:

```bash
# List configured jobs
poetry run python scheduler.py --list

# Check next run times
poetry run python scheduler.py --status

# Run a single job immediately
poetry run python scheduler.py --run lastfm

# Start scheduler daemon
poetry run python scheduler.py
```

For production, install the systemd service:

```bash
sudo cp docs/lifestream-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lifestream-scheduler
```

### Manual / Crontab (Legacy)

Individual import scripts can be run directly:

```bash
cd imports
poetry run python lastfm.py
```

See `docs/crontab.example` for cron-based scheduling using `bin/run_import.sh`.

## Project Structure

```
scheduler.py          # Main scheduler daemon
config.ini            # Configuration (not in repo)
schema.sql            # Database schema

imports/              # Import scripts for each service
  lifestream/         # Core library
    __init__.py       # Config, logging, argument parsing
    cache.py          # Redis caching utilities
    db.py             # Database connection and EntryStore
    jobs.py           # Job execution functions
    notifications.py  # Email/Slack notification sending
    
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
