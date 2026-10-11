# Word Search Solver API

A Python/FastAPI service that searches rectangular letter grids in all eight
directions. Structured JSON solving is deterministic and does not require an
LLM. The image endpoint recognizes letters locally using Tesseract and OpenCV,
without an API key or network request. A remote OpenAI-compatible vision
gateway remains an explicit opt-in alternative.

## Requirements

- Python 3.11 or newer
- Local image extraction requires Tesseract 5 with English (`eng`) language data.
  Tesseract is already installed on this workspace machine.
- For the optional remote provider only: an approved HTTPS Route-LLM-compatible
  endpoint, a rotated API key, and an enabled vision-capable model.

## Install and run

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the generated API documentation.

See [API-Test-Use-Cases.md](./API-Test-Use-Cases.md) for Swagger/Postman
instructions, ready-to-use payloads, expected results, and negative tests.

## Run with Docker Compose

Docker Compose builds the API image with Tesseract and English language data,
starts the service on port `8765`, and checks readiness through `GET /health`:

```powershell
docker compose up --build -d
Invoke-RestMethod http://127.0.0.1:8765/health
docker compose down
```

The health endpoint returns `{"status":"ok"}` after the API is accepting
requests. The image bundles the local OCR engine, so image solving works with
the default `IMAGE_EXTRACTION_PROVIDER=local` setting. To use a different
host-side port, set `HOST_PORT` before starting Compose. Optional image and
Route-LLM settings can also be supplied through environment variables; keep
API keys out of source control and provide them only in the runtime environment.

For submission, place the project contents under exactly one top-level folder
in the ZIP and keep `docker-compose.yml` directly inside that folder. Do not
include `.git`, `.venv`, `.env`, or cache directories. Keep the archive below
the applicable contest size limit. The repository's `GET /health`,
`POST /api/v1/solve`, and `POST /api/v1/solve/image` endpoints are documented
in this README and in `API-Test-Use-Cases.md`; use the problem-provided Karate
`.feature` file as the final contract when one is available.

Karate contract features derived from the checked-in use cases are in
[`tests/karate`](./tests/karate). Run them with the evaluator's Karate runner
after starting the API, add `tests/karate` to the Karate classpath so its
configuration and worksheet fixture are available, and set the `baseUrl`
system property if the API is not at `http://127.0.0.1:8765`.

## Solve from a grid

```http
POST /api/v1/solve
Content-Type: application/json
```

```json
{
  "grid": [
    ["C", "A", "T"],
    ["D", "O", "G"]
  ],
  "words": ["cat", "DOG", "MOUSE"]
}
```

Grid cells and target words accept ASCII A-Z letters and are case-insensitive.
Words are trimmed, converted
to uppercase, and duplicate targets are removed while retaining their first
appearance. Every word is searched in all eight straight-line directions. If
a word has more than one occurrence, the API returns the first match found in
row-major start-cell order, followed by north, northeast, east, southeast,
south, southwest, west, and northwest direction order. Single-letter matches
use `north` with identical start/end coordinates.

Grids have 1-100 rows and columns; requests accept up to 200 target words of
1-100 letters. JSON request bodies are capped at 256 KiB. Oversized requests
are rejected before parsing.

Coordinates in the response are zero-based. `results` contains found words;
`not_found` lists requested words that were not present.

## Solve from an image

### Local OCR (default, no API key)

`IMAGE_EXTRACTION_PROVIDER=local` is the default. Tesseract is located on PATH
or in the usual Windows installation directories. If installed elsewhere, set
the executable path:

```powershell
$env:IMAGE_EXTRACTION_PROVIDER = "local"
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

On another machine, install Tesseract with English data using your OS package
manager or an approved installer; the Python packages alone do not install the
engine. Linux typically provides it through `tesseract-ocr` and
`tesseract-ocr-eng`; on macOS, the Homebrew package is `tesseract`.

Upload an upright, clearly bordered grid containing evenly spaced letters with
at least 2 rows and 2 columns. The detector identifies a rectangular grid and
corrects modest perspective skew, then thresholds and recognizes individual
cells. It does not use the requested word list to guess letters or repair the
image. Handwriting, borderless grids, severe rotation/glare, and uneven layouts
are not supported by the initial local provider; use a sharper cropped photo
with the outer border visible, or submit the letters to the JSON endpoint.

All preprocessing and recognition happen locally, with input piped directly
to Tesseract. No uploaded image or crop is written to disk by the application.
`LOCAL_OCR_TIMEOUT_SECONDS` bounds the whole extraction (default 60 seconds).
Recognition time grows with the number of cells.

The image endpoint accepts a multipart image and `words` as a JSON-array form
field:

Swagger's **Try it out** also supports this format. The API declares the
`words` part as `application/json` so Swagger preserves the brackets and
quotes instead of sending comma-separated text. Both ordinary JSON-array
text fields and JSON multipart file parts are accepted; comma-separated
words are not valid input.

The Compose service limits Tesseract to one OpenMP thread per invocation.
This avoids thread oversubscription during the many small cell-recognition
calls in Docker Desktop.

```python
import httpx

with open("puzzle.png", "rb") as image:
    response = httpx.post(
        "http://127.0.0.1:8000/api/v1/solve/image",
        files={"image": ("puzzle.png", image, "image/png")},
        data={"words": '["BEAR", "FROG"]'},
        timeout=90,
    )
response.raise_for_status()
print(response.json())
```

The response includes the extracted grid, a provider confidence score, and the
solver result. For local OCR, confidence is the mean accepted cell score from
Tesseract, not a calibrated probability. Cells with no valid single-letter
recognition or a best score below 0.5 are rejected. The overall mean must meet
`EXTRACTION_CONFIDENCE_THRESHOLD` (default 0.7).
Confidence is **not calibrated or a guarantee** for either provider: letters
may be misread despite a high score. Always inspect the returned grid; correct
it and resubmit to the JSON endpoint if needed.

Multipart uploads are bounded
before parsing to the image byte limit plus 64 KiB for form overhead.
Only single-frame JPEG, PNG, GIF, and WebP images are supported.

Limits are configurable with `IMAGE_MAX_BYTES`, `IMAGE_MAX_WIDTH`, and
`IMAGE_MAX_HEIGHT`; defaults are 5 MiB and 4096 pixels per dimension. The
minimum accepted extraction confidence is configurable with
`EXTRACTION_CONFIDENCE_THRESHOLD` (default `0.7`). Set the optional environment
variables in `.env.example` in the process environment; the application does
not automatically load `.env` files.

### Optional remote gateway

Select this provider explicitly; merely setting an API key does not activate it:

```powershell
$env:IMAGE_EXTRACTION_PROVIDER = "route_llm"
$env:ROUTE_LLM_BASE_URL = "https://your-gateway.example/v1"
$env:ROUTE_LLM_API_KEY = "<your-rotated-key>"
$env:ROUTE_LLM_MODEL = "<vision-enabled-model>"
```

Image data is sent to the gateway **only** when `route_llm` is selected. Verify
approval, model support, and authoritative gateway image limits before use.
The documented HTTP endpoint is not accepted except on loopback. The credential
in the original source photos was exposed; rotate/revoke it instead of copying
it into code. A paid GitHub Copilot subscription does not supply an
OpenAI-compatible application API key for this backend.

Set `IMAGE_EXTRACTION_PROVIDER=disabled` to disable image extraction entirely.

## Errors and deployment boundaries

- `400`: empty, corrupt, or invalid image.
- `413`: request, upload, or image dimensions exceed limits.
- `415`: unsupported, mismatched, or animated image format.
- `422`: invalid grid, words, or required multipart fields.
- `502`: extraction failed, timed out, was truncated, or returned invalid/uncertain data.
- `503`: image extraction is disabled, Tesseract is missing, or provider settings
  are invalid/unconfigured.

The local development API has no authentication or per-client rate limiting.
Do not expose it publicly without an authenticating, rate-limiting reverse
proxy, TLS, and appropriate concurrency/memory limits. Do not enable verbose
HTTP-client logging in deployments containing credentials or user images.

## Worksheet fixture

The supplied worksheet has row 7 `S L Y C R A B D` (one-based numbering).
The initial transcription read its second letter as `I`; checking the image
shows `L`, which completes `SEAL` down column 2. Tests use the corrected grid
and verify all ten targets. A real local-OCR regression test compares every
one of the 64 letters extracted from the supplied photograph, not only the
found words. The JSON solver never alters submitted letters to make words fit.

## Endpoints

- `GET /health` — non-sensitive process health response.
- `POST /api/v1/solve` — deterministic JSON-grid solving.
- `POST /api/v1/solve/image` — local OCR (or opt-in remote vision), then solving.
- `GET /docs` — interactive OpenAPI documentation.

## Development checks

You can also use the VS Code task **Run Word Search API**, which starts the
service at `http://127.0.0.1:8765`.

```powershell
python -m pytest
python -m ruff check .
python -m mypy app
```

The mypy target is Python 3.12 because the current NumPy type stubs use modern
type-statement syntax. The current runtime validation uses Python 3.14.
Real local recognition tests are marked `local_ocr` and run automatically when
Tesseract and the supplied photo are available; skip them explicitly with
`python -m pytest -m "not local_ocr"` on hosts without the engine/fixture.
All remote-provider tests use mock HTTP transports and never send live requests.
