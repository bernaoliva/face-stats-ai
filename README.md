# Face Stats AI

Real-time face recognition system for live football broadcasts. Identifies players from camera feeds and automatically displays their statistics on broadcast graphics via Google Sheets (Flowics integration).

## How It Works

```
Camera Feed → Face Detection → Player Recognition → Stats Fetch → Broadcast Graphics
   (NDI/RTMP)    (MTCNN)      (InsightFace)       (Opta API)    (Google Sheets/Flowics)
```

1. **Capture** reads frames from a live video stream (NDI or RTMP)
2. **Recognition** detects faces and matches them against a player database using 512-dim embeddings
3. **Data Fetcher** pulls match/season stats from the Opta API and uses an LLM to select the 5 most relevant stats
4. **Sheets Writer** updates a Google Sheet with the player's name, photo, team logo, and stats — ready for Flowics to read

## Architecture

```
┌──────────────────────┐
│   CAPTURE SERVICE    │
│   NDI/RTMP Stream    │
│   Face Detection     │
└─────────┬────────────┘
          │ HTTP POST (base64 face crop)
          v
┌──────────────────────┐     ┌──────────────────────┐
│ RECOGNITION SERVICE  │     │ DATA FETCHER SERVICE  │
│ Port 8081            │     │ Port 8082             │
│                      │     │                       │
│ InsightFace buffalo_l│     │ Opta API (MA2/MA3/TM4)│
│ Cosine similarity    │     │ LLM stat selection    │
│ Player DB (JSON/     │     │ Google Sheets writer  │
│   Firestore)         │     │                       │
└──────────────────────┘     └───────────────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Generate the player database

```bash
# From Google Sheets headshots (requires GCP service account)
python -m setup.register_from_sheets --output local_players.json

# Or from local photos
python -m setup.register_local --photos-dir ./photos --meta players_meta.json --output local_players.json
```

### 4. Test with local images

```bash
# Single image
python -m scripts.recognize_and_write --image photo.jpg --db local_players.json

# Simulate a live stream from a folder of images
python -m scripts.simulate_live \
  --images-dir ./test_frames \
  --db local_players.json \
  --fps 2 \
  --debounce 30 \
  --no-sheets
```

### 5. Run in production (Docker)

```bash
docker-compose up -d
```

## Project Structure

```
face-stats-ai/
├── capture/                # Video stream capture + face detection
│   ├── main.py             # Main pipeline (NDI/RTMP → detect → recognize → stats)
│   ├── stream_reader.py    # NDI and RTMP stream abstraction
│   ├── face_detector.py    # MTCNN face detection with margin
│   └── config.py           # Capture settings (FPS, debounce, source)
│
├── recognition/            # Face recognition microservice (FastAPI)
│   ├── main.py             # POST /recognize, GET /health
│   ├── face_embedder.py    # InsightFace buffalo_l (512-dim embeddings)
│   ├── matcher.py          # Cosine similarity matching
│   ├── local_player_db.py  # JSON-backed player database
│   ├── player_db.py        # Firestore-backed player database
│   └── Dockerfile
│
├── data_fetcher/           # Stats fetching microservice (FastAPI)
│   ├── main.py             # POST /stats, GET /health
│   ├── opta_client.py      # Opta SDAPI client (OAuth + URL key auth)
│   ├── opta_mock.py        # Realistic mock data for testing
│   ├── stats_selector.py   # LLM-powered stat selection (Groq/Gemini/fallback)
│   ├── sheets_writer.py    # Google Sheets writer (Flowics layout)
│   └── Dockerfile
│
├── setup/                  # Database generation tools
│   ├── register_from_sheets.py  # Build DB from Google Sheets headshots
│   ├── register_local.py        # Build DB from local photo folders
│   └── enrich_db.py             # Add extra photos to improve recognition
│
├── scripts/                # Testing and demo scripts
│   ├── simulate_live.py         # Folder-based live stream simulation
│   └── recognize_and_write.py   # Single image end-to-end test
│
├── shared/                 # Shared models and utilities
│   ├── models.py           # Pydantic models (PlayerInfo, StatItem, etc.)
│   ├── opta_config.py      # Opta API config + URL builder
│   └── gcp_utils.py        # Cached GCP clients
│
├── tests/                  # Test suite
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Key Technologies

| Component | Technology |
|-----------|-----------|
| Face Detection | MTCNN (via facenet-pytorch) |
| Face Recognition | InsightFace buffalo_l (ResNet-50, 512-dim embeddings) |
| Similarity | Cosine similarity on L2-normalized vectors |
| Stats API | Opta SDAPI (MA2, MA3, TM4 feeds) |
| LLM | Groq (llama-3.3-70b) or Gemini 2.0 Flash |
| Broadcast | Google Sheets → Flowics |
| Services | FastAPI + Docker Compose |
| Video | NDI (via NDIlib) or RTMP (via OpenCV) |

## API Endpoints

### Recognition Service (`:8081`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service status + player count |
| POST | `/recognize` | Recognize a face (base64 image → player match) |
| POST | `/reload` | Reload player database for a new match |

### Data Fetcher Service (`:8082`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service status |
| POST | `/stats` | Fetch + select stats → write to Sheets |

## Improving Recognition

The player database starts with one headshot per player. Recognition accuracy improves significantly by adding real match photos:

```bash
# Put extra photos in a folder (named after the player)
# e.g., extra_photos/Cano_match1.jpg, extra_photos/PH_Ganso_tv.jpg

python -m setup.enrich_db --extra extra_photos/ --db local_players.json
```

The script handles accent normalization (`Ignacio` → `Ignácio`) and suffix stripping (`Cano_jogo` → `Cano`).

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `OPTA_AUTH_METHOD` | `url_key` or `oauth` |
| `OPTA_USE_MOCK` | `true` for testing without API access |
| `LLM_PROVIDER` | `groq`, `gemini`, or `fallback` |
| `GROQ_API_KEY` | Free tier at [console.groq.com](https://console.groq.com) |
| `SHEETS_SPREADSHEET_ID` | Google Sheets ID for Flowics output |
| `PLAYER_DB_MODE` | `local` (JSON) or `firestore` |
| `CAPTURE_SOURCE` | `ndi` or `rtmp` |
| `CAPTURE_FPS` | Frames per second (default: 2) |
| `CAPTURE_DEBOUNCE_SECONDS` | Min seconds between same player (default: 30) |

## Testing

```bash
pytest -v
```

## License

Private project — all rights reserved.
