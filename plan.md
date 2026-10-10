# Word Search Solver API — Implementation Plan

## 1. Goal

Build a Python service with FastAPI that accepts a word-search puzzle, finds the requested words, and returns their locations. Support structured grid input as the reliable baseline and image upload as an optional convenience that extracts a grid before solving.

## 2. Source review and interpretation

- **`Animal Image.jpeg`** is a photo of an unfilled 4-letter Animals worksheet. It shows an 8 × 8 letter grid and these ten target words: `BEAR`, `CRAB`, `DUCK`, `FISH`, `FROG`, `GOAT`, `LION`, `SEAL`, `SWAN`, and `WOLF`. The image is a useful sample/acceptance fixture, but photo perspective and screen artifacts make it unsuitable as the only source of truth for OCR.
- **`Route-LLM-guide-content.md`** transcribes a Route-LLM OpenAI-compatible API guide. Relevant capabilities include chat completions, multimodal messages using Base64 data URLs, and function/tool calling. The guide notes that vision support depends on both the chosen model and gateway configuration; image limits and model availability must be confirmed against the deployed service.
- **`WordSearchSolverAPIDoc.pdf`** has two pages and no extractable text. It is an image-only PDF of overlapping API-guide screenshots; treat it as supporting visual material, not as a separate source of requirements. The readable Markdown transcription is the primary reference for that guide.
- Overlapping guide screenshots are consolidated rather than counted as separate requirements. The API key visible in a source image is exposed and must be revoked/rotated. Do not copy it into this project, the plan, tests, logs, or documentation.

## 3. Assumptions and boundaries

- The primary product is a word-search solver, not a general-purpose Route-LLM client.
- The solver itself is deterministic and does not require an LLM. LLM/vision use is isolated to optional image-to-grid extraction.
- The initial API supports either a grid and target words supplied as JSON or a puzzle image plus target words. Image-only discovery of the word list is out of scope for the initial release.
- Store the Route-LLM base URL, API key, and vision-capable model in environment-based configuration. Never use credentials transcribed from the screenshots. Require HTTPS outside local development.
- Do not persist uploaded images or puzzle data in the first version.
- Confirm the exact OCR/vision model, gateway access, image limits, and whether image extraction is in the first release before implementation.

## 4. Functional requirements

1. Validate and normalize a rectangular grid of single-letter cells.
2. Normalize target words (trim whitespace and use uppercase); reject empty or malformed requests.
3. Search each target in all eight straight-line directions: horizontal, vertical, and diagonal, forwards and backwards.
4. Return each found word with start/end coordinates and direction; report missing words explicitly.
5. Offer an image-upload path that extracts a grid and reports extraction failures clearly rather than returning guessed or success-shaped results.
6. Provide a health endpoint and generated OpenAPI documentation.
7. Keep solver behavior independent of the LLM provider so the structured-input API works when the gateway is unavailable.

## 5. Proposed API

### `POST /api/v1/solve`

Accept JSON:

```json
{
  "grid": [
    ["J", "F", "R", "O", "G", "J", "Y", "I"],
    ["D", "G", "O", "A", "T", "Y", "W", "M"]
  ],
  "words": ["FROG", "GOAT"]
}
```

The example is intentionally abbreviated; a real grid must contain all rows and have the same number of columns in every row.

Return JSON shaped like:

```json
{
  "grid_size": {"rows": 2, "columns": 8},
  "results": [
    {
      "word": "FROG",
      "found": true,
      "start": {"row": 0, "column": 1},
      "end": {"row": 0, "column": 4},
      "direction": "east"
    },
    {
      "word": "GOAT",
      "found": true,
      "start": {"row": 1, "column": 1},
      "end": {"row": 1, "column": 4},
      "direction": "east"
    }
  ],
  "not_found": []
}
```

Coordinates are zero-based and identify cells in the submitted grid. Document this convention in the API schema.

### `POST /api/v1/solve/image`

- Accept one image upload (`multipart/form-data`) and a target-word list.
- Validate content type, encoded file size, and image dimensions against configurable limits before forwarding or decoding.
- Extract the grid through a provider interface backed by an OpenAI-compatible vision endpoint. Pass image content as a Base64 data URL only if that is what the configured gateway requires.
- Return the extracted grid alongside the solver results so clients can inspect and correct recognition.
- If extraction is ambiguous, unavailable, or invalid, return an explicit error with no fabricated solution. Consider a future user-confirmation/edit step before solving uncertain grids.

### `GET /health`

Return service status without exposing environment variables, credentials, or detailed infrastructure information.

## 6. Suggested project structure

```text
app/
  main.py                 # FastAPI app and router registration
  api/
    routes.py             # Health and solve endpoints
  schemas/
    puzzle.py             # Pydantic request/response models
  services/
    solver.py             # Pure grid-search algorithm
    extraction.py         # Image extraction interface and orchestration
    route_llm.py          # OpenAI-compatible vision adapter
  core/
    config.py             # Environment-backed settings
tests/
  test_solver.py
  test_api.py
  test_extraction.py
.env.example              # Placeholder settings only; never real credentials
pyproject.toml            # Dependencies and development/test configuration
README.md                 # Setup, API examples, security and limitations
```

Keep the solver as a pure function with no FastAPI, network, or provider dependency. Keep image parsing and gateway requests behind the extraction adapter.

## 7. Implementation phases

### Phase 1 — Confirm behavior and contracts

- Confirm whether image extraction is required in the first release or can follow the JSON solver.
- Agree on supported image formats, maximum dimensions/size, coordinate convention, duplicate-word handling, and whether words may appear in reverse.
- Verify available vision-enabled model and gateway settings with the service owner; do not infer them solely from the screenshots.

### Phase 2 — Build the deterministic solver

- Add typed Pydantic schemas and input validation.
- Implement a direction-vector search over eight directions, with bounds checks and a documented policy for repeated words or multiple matches.
- Add focused unit tests for all directions, boundaries, absent words, one-letter words, case/whitespace normalization, ragged grids, and the worksheet fixture.

### Phase 3 — Expose the JSON API

- Add `POST /api/v1/solve` and `GET /health`.
- Return stable, documented response shapes and appropriate `4xx` validation errors.
- Add API tests using FastAPI's test client; verify generated OpenAPI schema.

### Phase 4 — Add optional image extraction

- Add upload validation and configurable size/dimension limits.
- Define a provider contract for converting an image into a rectangular grid; implement the Route-LLM-compatible adapter only after confirming endpoint, model, authentication, and image support.
- Read secrets only from runtime configuration. Reject insecure remote transport in production; never log authorization headers, API keys, Base64 image data, or full uploaded content.
- Validate the extracted grid with the same schema as JSON input before solving. Surface low confidence or malformed output as an extraction error.
- Test with mocked provider responses; keep tests independent of live credentials/network. Add an opt-in integration test only if a safe test environment is available.

### Phase 5 — Documentation and operational checks

- Document local setup, configuration, request/response examples, errors, image limitations, and the fact that image recognition may be uncertain.
- Add `.env.example` with placeholders only; ensure `.env` and uploaded test images are excluded from version control where applicable.
- Run formatter/linter, type checks, unit/API tests, and a local smoke test for both JSON solving and image-upload validation.

## 8. Acceptance criteria

- The full worksheet grid and its ten listed words produce correct locations or explicit `not_found` results that can be checked against the grid.
- Every supported direction is verified by tests, including reverse and diagonal matches.
- Invalid/non-rectangular grids, invalid words, oversized uploads, unsupported formats, and failed extraction receive explicit client errors.
- The JSON solver operates without an API key, external network access, or an LLM.
- Image extraction can be disabled or unavailable without breaking the core solve API.
- No real API key, authorization header, uploaded image content, or secret-bearing configuration is committed or logged.
- The API's coordinate system, image-processing limits, and model/gateway prerequisites are documented.

## 9. Risks and decisions to resolve before image integration

- The source guide is a transcription of a gateway document, not a guarantee that the pictured model or account currently supports image input.
- The photographed limits are difficult to read and may be stale; obtain authoritative limits before configuring upload validation.
- The worksheet photo is a photograph of a displayed worksheet, so perspective, glare, and screen artifacts can impair grid extraction. The service must expose extracted letters for review and avoid silently presenting uncertain OCR as fact.
- The source guide shows an HTTP endpoint. Do not send bearer credentials over untrusted networks; obtain an HTTPS endpoint or use a protected private network before enabling remote integration.
- Revoke/rotate the API key visible in the source photo before any implementation or testing uses that account.

## 10. Implementation status

- **Phase 1:** Implemented documented defaults: ASCII A-Z, eight directions,
  zero-based coordinates, normalized/deduplicated words, first deterministic
  match per word, and optional image extraction disabled without configuration.
  Live gateway/model availability remains unverified.
- **Phase 2:** Implemented the deterministic solver, typed validation, input
  limits, and all-direction/unit tests. Rechecking the worksheet corrected
  row 7 column 2 from `I` to `L`; all ten word locations are verified.
- **Phase 3:** Implemented JSON solving, health, OpenAPI documentation, and
  HTTP tests. JSON solving is independent of gateway settings.
- **Phase 4:** Implemented the provider interface and async OpenAI-compatible
  adapter, pre-parser body limits, validated single-frame image uploads,
  HTTPS enforcement, confidence checks, timeouts, and explicit errors.
  Provider tests use a mocked HTTP transport; no source images or credentials
  are sent to external services during validation.
- **Phase 5:** Added dependency metadata, development tooling, configuration
  template, ignore rules, setup/API/security documentation, and automated
  checks. Actual OCR accuracy and gateway limits require an approved live
  integration test with a rotated credential and confirmed HTTPS endpoint.

See `README.md` for setup and commands. This is a local-development service;
public deployment requires authentication, rate limiting, and TLS.

### Verification results

- 96 automated tests passed, including exact positions for all ten worksheet
  words, all eight directions, upload boundaries, and mocked gateway failures.
- Ruff lint and formatting checks passed; strict mypy passed for app and tests.
- Dependency consistency check passed.
- Live local server smoke checks passed for health, JSON solving, OpenAPI, and
  the image endpoint's explicit `503` response when no provider is configured.
- One upstream Starlette test-client deprecation warning remains; it does not
  affect test results. No live model/image-recognition accuracy claim is made.

### Local OCR follow-up

At the user's request, the default image provider now uses local OpenCV
border/grid detection, perspective correction, and Tesseract recognition.
It requires no API key and sends no image data to a remote service.
The supplied photo has been recognized with an exact match for all 64 cells.
This result is specific to the fixture, not a guarantee for arbitrary photos.
Local OCR requires a clear outer border, evenly spaced printed A-Z letters,
and at least 2 rows and columns. Provider selection is explicit:
`IMAGE_EXTRACTION_PROVIDER=local` (default), `route_llm`, or `disabled`.
See `README.md` for Tesseract installation, limits, and recognition caveats.

Local-provider verification: 108 tests passed; Ruff and strict mypy passed.
A real request to the local `/api/v1/solve/image` endpoint returned HTTP 200,
recognized all 64 worksheet letters exactly, and found all ten animal words.
The measured request took approximately 21 seconds and returned an OCR score
of 0.8835. No external gateway or API key was used.
