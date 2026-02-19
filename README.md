# Pingboard

URL status monitoring dashboard. Periodically checks configured URLs and serves results through a FastAPI web interface.

## Setup

```bash
pip install -r requirements.txt
```

## Running

```bash
make dev
```

This starts the FastAPI server on `http://127.0.0.1:8000` with the background URL checker active.

## Configuration

URLs to monitor are defined in `urls.json`:

```json
{
  "interval_seconds": 30,
  "urls": [
    "https://example.com",
    "https://httpbin.org/status/200"
  ]
}
```

| Field              | Description                              |
|--------------------|------------------------------------------|
| `interval_seconds` | How often to check each URL (in seconds) |
| `urls`             | List of URLs to monitor                  |

## API

- `GET /status` — Returns JSON with the latest check result and recent history for each monitored URL.
