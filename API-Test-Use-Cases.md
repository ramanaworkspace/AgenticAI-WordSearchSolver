# Word Search API: Test Use Cases and Payloads

## 1. Test setup

- Base URL: `http://127.0.0.1:8765`
- Swagger UI: `http://127.0.0.1:8765/docs`
- Health check: `GET /health`, expected HTTP `200` and `{"status":"ok"}`.
- Local OCR requires Tesseract with English language data. No API key is needed.

| Method and endpoint | Request format | Purpose |
|---|---|---|
| `POST /api/v1/solve` | `application/json` | Solve a manually supplied grid. |
| `POST /api/v1/solve/image` | `multipart/form-data` | Recognize letters from an uploaded image, then solve. |

Coordinates are **zero-based**: `(0, 0)` is the top-left cell.
Words and grid letters are normalized to uppercase. Duplicate target words
are consolidated. Matching searches all eight straight-line directions.
Each word returns its first match in row-major start-cell order, then direction
order: north, northeast, east, southeast, south, southwest, west, northwest.
Missing words appear in `not_found`, not as results with `found: false`.

## 2. JSON solver tests

In Swagger, expand `POST /api/v1/solve`, click **Try it out**, paste a
payload into the request body, and click **Execute**.

In Postman, use the same endpoint with **Body > raw > JSON**.
Set `Content-Type: application/json`.

### JSON-01: Found and missing words

**Request:**

```json
{
  "grid": [
    ["C", "A", "T"],
    ["D", "O", "G"]
  ],
  "words": ["CAT", "DOG", "MOUSE"]
}
```

**Expected:** HTTP `200` with this response:

```json
{
  "grid_size": {
    "rows": 2,
    "columns": 3
  },
  "results": [
    {
      "word": "CAT",
      "found": true,
      "start": {"row": 0, "column": 0},
      "end": {"row": 0, "column": 2},
      "direction": "east"
    },
    {
      "word": "DOG",
      "found": true,
      "start": {"row": 1, "column": 0},
      "end": {"row": 1, "column": 2},
      "direction": "east"
    }
  ],
  "not_found": ["MOUSE"]
}
```

### JSON-02: Diagonal and reverse matching

**Request:**

```json
{
  "grid": [
    ["C", "X", "X"],
    ["X", "A", "X"],
    ["X", "X", "T"]
  ],
  "words": ["CAT", "TAC"]
}
```

**Expected:** HTTP `200`, `not_found: []`, and these matches:

| Word | Start `(row, column)` | End `(row, column)` | Direction |
|---|---|---|---|
| CAT | `(0, 0)` | `(2, 2)` | southeast |
| TAC | `(2, 2)` | `(0, 0)` | northwest |

### JSON-03: Normalization and duplicate targets

**Request:**

```json
{
  "grid": [
    [" c ", "a", "t"]
  ],
  "words": [" cat ", "CAT", "Cat"]
}
```

**Expected:** HTTP `200`, exactly one result for `CAT`, start `(0, 0)`,
end `(0, 2)`, direction `east`, and `not_found: []`.

### JSON-04: Single-letter word

**Request:**

```json
{
  "grid": [
    ["A", "B", "C"]
  ],
  "words": ["B"]
}
```

**Expected:** HTTP `200`, one match for `B`, start and end both `(0, 1)`,
direction `north`.

### JSON-05: Multiple occurrences

**Request:**

```json
{
  "grid": [
    ["C", "A", "T", "C", "A", "T"]
  ],
  "words": ["CAT"]
}
```

**Expected:** HTTP `200`, exactly one result, start `(0, 0)`, end `(0, 2)`,
direction `east`.

### JSON-06: Full animal worksheet

**Request:**

```json
{
  "grid": [
    ["J", "F", "R", "O", "G", "J", "Y", "I"],
    ["D", "G", "O", "A", "T", "Y", "W", "M"],
    ["M", "U", "X", "C", "B", "V", "O", "L"],
    ["L", "S", "C", "I", "E", "J", "L", "I"],
    ["B", "E", "A", "K", "A", "S", "F", "O"],
    ["Q", "A", "E", "D", "R", "W", "D", "N"],
    ["S", "L", "Y", "C", "R", "A", "B", "D"],
    ["F", "I", "S", "H", "Z", "N", "J", "H"]
  ],
  "words": [
    "BEAR", "CRAB", "DUCK", "FISH", "FROG",
    "GOAT", "LION", "SEAL", "SWAN", "WOLF"
  ]
}
```

**Expected:** HTTP `200`, grid size `8 x 8`, ten results, and `not_found: []`.

| Word | Start `(row, column)` | End `(row, column)` | Direction |
|---|---|---|---|
| BEAR | `(2, 4)` | `(5, 4)` | south |
| CRAB | `(6, 3)` | `(6, 6)` | east |
| DUCK | `(1, 0)` | `(4, 3)` | southeast |
| FISH | `(7, 0)` | `(7, 3)` | east |
| FROG | `(0, 1)` | `(0, 4)` | east |
| GOAT | `(1, 1)` | `(1, 4)` | east |
| LION | `(2, 7)` | `(5, 7)` | south |
| SEAL | `(3, 1)` | `(6, 1)` | south |
| SWAN | `(4, 5)` | `(7, 5)` | south |
| WOLF | `(1, 6)` | `(4, 6)` | south |

### JSON-07: Reject a non-rectangular grid

**Request:**

```json
{
  "grid": [
    ["A", "B"],
    ["C"]
  ],
  "words": ["ABC"]
}
```

**Expected:** HTTP `422`; the validation error identifies unequal row lengths.

### JSON-08: Reject a malformed word

**Request:**

```json
{
  "grid": [
    ["C", "A", "T"]
  ],
  "words": ["CAT1"]
}
```

**Expected:** HTTP `422`; target words must contain ASCII A-Z letters only.

### JSON-09: Reject empty input

Test each request separately:

```json
{"grid": [], "words": ["CAT"]}
```

```json
{"grid": [["C", "A", "T"]], "words": []}
```

```json
{"grid": [["C", "A", "T"]], "words": [""]}
```

**Expected:** HTTP `422` for each request.

### JSON-10: Reject a multi-letter grid cell

```json
{
  "grid": [["CAT"]],
  "words": ["CAT"]
}
```

**Expected:** HTTP `422`; every cell must contain exactly one A-Z letter.

### JSON input limits

- Grid: 1-100 rows, each with the same number of columns (1-100).
- Target words: at least one, at most 200 entries before deduplication.
- Word length: 1-100 letters.
- JSON request body: at most 256 KiB.
- Unsupported extra JSON properties are rejected.

Oversized request bodies return `413`; invalid field values/lengths return `422`.

## 3. Image solver tests

### Request format

`POST /api/v1/solve/image` accepts these **multipart form fields**:

| Field | Type | Example |
|---|---|---|
| `image` | File | `Animal Image.jpeg` |
| `words` | Text containing a JSON array | `["BEAR","FROG"]` |

Do not send the image endpoint a JSON object. Do not enter `BEAR,FROG` or
a Python-style list such as `['BEAR','FROG']` in the words field.
Use valid JSON with double quotes.

### Swagger instructions

1. Open `http://127.0.0.1:8765/docs`.
2. Expand `POST /api/v1/solve/image`.
3. Click **Try it out**.
4. Choose [Animal Image.jpeg](./Animal%20Image.jpeg) in the **image** field.
5. Paste the target-word JSON array into the **words** field.
6. Click **Execute**.
7. Allow approximately 20-35 seconds for the worksheet on this machine.
   Timing varies with the image, grid size, and machine load.

### Postman instructions

1. Set method to `POST`.
2. Use `http://127.0.0.1:8765/api/v1/solve/image`.
3. Select **Body > form-data**.
4. Add `image` as **File**, and select the worksheet image.
5. Add `words` as **Text**, containing the JSON array.
6. Do not manually set the Content-Type header; Postman supplies the multipart
   boundary.
7. Allow a request timeout of at least 90 seconds for local OCR testing.

### IMAGE-01: Recognize and solve the full worksheet

**File:** [Animal Image.jpeg](./Animal%20Image.jpeg)

**words field:**

```json
["BEAR","CRAB","DUCK","FISH","FROG","GOAT","LION","SEAL","SWAN","WOLF"]
```

**Expected:** HTTP `200`.

- `grid` contains the exact grid supplied in JSON-06.
- `solution.grid_size` is `{"rows":8,"columns":8}`.
- `solution.results` contains the ten locations listed in JSON-06.
- `solution.not_found` is `[]`.
- `confidence` is between the configured threshold and `1`.

Do not compare confidence to an exact fixed value; it can vary with Tesseract
version and preprocessing. Confidence is a recognition score, not a guarantee
or calibrated probability. Inspect all returned letters.

### IMAGE-02: Find only selected words

**File:** Animal worksheet.

**words field:**

```json
["BEAR","FROG"]
```

**Expected:** HTTP `200`, two results, and `solution.not_found: []`.
The recognized grid remains the full worksheet grid.

### IMAGE-03: Include a word absent from the puzzle

**File:** Animal worksheet.

**words field:**

```json
["BEAR","ZEBRA"]
```

**Expected:** HTTP `200`, one result for `BEAR`, and:

```json
{
  "not_found": ["ZEBRA"]
}
```

The fragment above is the expected `solution.not_found` field, not the entire
response.

### IMAGE-04: Normalize and deduplicate targets

**File:** Animal worksheet.

**words field:**

```json
["bear","BEAR"," frog "]
```

**Expected:** HTTP `200`, exactly two results: `BEAR` and `FROG`.

### Image negative tests

| ID | File / condition | words field | Expected HTTP status |
|---|---|---|---|
| IMAGE-05 | Valid worksheet | `BEAR,FROG` | `422`: not a JSON array. |
| IMAGE-06 | Valid worksheet | `[]` | `422`: no target words. |
| IMAGE-07 | Valid worksheet | `["CAT1"]` | `422`: invalid word. |
| IMAGE-08 | Omit the image field entirely | `["BEAR"]` | `422`: required field missing. |
| IMAGE-09 | Upload a text file declared as `text/plain` | `["BEAR"]` | `415`: unsupported media type. |
| IMAGE-10 | Upload invalid bytes declared as `image/jpeg` | `["BEAR"]` | `400`: invalid image. |
| IMAGE-11 | Upload an empty file declared as `image/png` | `["BEAR"]` | `400`: empty image. |
| IMAGE-12 | Upload PNG content declared as `image/jpeg` | `["BEAR"]` | `415`: declared type does not match content. |
| IMAGE-13 | Valid image larger than 5 MiB | `["BEAR"]` | `413`: default upload byte limit. |
| IMAGE-14 | Valid image wider or taller than 4096 pixels | `["BEAR"]` | `413`: default dimension limit. |
| IMAGE-15 | Valid white PNG with no grid | `["BEAR"]` | `502`: no detectable grid. |
| IMAGE-16 | Multi-frame animated GIF | `["BEAR"]` | `415`: animated images are unsupported. |
| IMAGE-17 | Local OCR engine missing/invalid `TESSERACT_CMD` | `["BEAR"]` | `503`: local engine unavailable. |
| IMAGE-18 | `IMAGE_EXTRACTION_PROVIDER=disabled` | `["BEAR"]` | `503`: extraction disabled. |

Byte and dimension limits can be changed through environment settings.
Multipart request bodies are bounded to the image limit plus 64 KiB of form
overhead before parsing. For type-related tests, explicitly set the uploaded
part's media type; relying on a filename extension alone can produce a
different validation error.

## 4. Executable request examples

### PowerShell: JSON solver

```powershell
$payload = @{
    grid = @(
        @("C", "A", "T"),
        @("D", "O", "G")
    )
    words = @("CAT", "DOG", "MOUSE")
} | ConvertTo-Json -Depth 5

$result = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8765/api/v1/solve" `
    -Method Post `
    -ContentType "application/json" `
    -Body $payload

$result | ConvertTo-Json -Depth 6
```

### Python: image solver

Run from the workspace folder using its Python environment. The application
already depends on `httpx`.

```python
import json

import httpx

words = [
    "BEAR", "CRAB", "DUCK", "FISH", "FROG",
    "GOAT", "LION", "SEAL", "SWAN", "WOLF",
]

with open("Animal Image.jpeg", "rb") as image:
    response = httpx.post(
        "http://127.0.0.1:8765/api/v1/solve/image",
        files={"image": ("puzzle.jpeg", image, "image/jpeg")},
        data={"words": json.dumps(words)},
        timeout=90,
    )

print("HTTP status:", response.status_code)
print(json.dumps(response.json(), indent=2))
response.raise_for_status()
```

## 5. Image quality and troubleshooting

- The default provider is local OCR; no API key or external gateway is used.
- The initial local recognizer requires a visible outer border, evenly spaced
  printed A-Z letters, and at least two rows and two columns.
- Prefer an upright, sharp photo with the outer grid border visible.
- Borderless grids, handwriting, severe rotation/glare, and uneven layouts
  are not supported by the initial local provider.
- OCR has a total timeout configured by `LOCAL_OCR_TIMEOUT_SECONDS`
  (default 60 seconds).
- If recognition fails, upload a clearer image or enter the grid through
  `/api/v1/solve`.
- If letters are misread, correct the returned grid and resubmit it to the
  JSON solver. The service does not repair letters using the target words.

See [README.md](./README.md) for provider configuration and setup.
Automated coverage is in [tests](./tests).
