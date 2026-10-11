# Learner Submission Guidelines

This document explains how to prepare and submit a project for automated evaluation. It covers practical steps, common pitfalls, and debugging tips to help ensure a reliable evaluation run.

## Quick summary

- Package the project as a ZIP containing exactly one top-level folder (the project folder).
- Put `docker-compose.yml` directly inside that folder; it must build and start the service.
- Expose a working HTTP API and implement an unauthenticated `GET /health` endpoint that returns HTTP 200.
- Implement the endpoints and response shapes asserted by the provided `.feature` file exactly.
- Upload through the web UI. Evaluation runs in the background and provides downloadable artifacts and an HTML Karate report.

## Before you start

- Confirm `GET /health` returns HTTP 200 within a few seconds after startup.
- Confirm the endpoints and response bodies required by the problem's PDF or `.feature` file are implemented.

## ZIP file structure

The ZIP must have exactly one top-level folder. The evaluator rejects ZIPs that:

- Put files at the ZIP root (for example, `docker-compose.yml` must be inside the single top-level folder).
- Contain multiple top-level folders.
- Nest `docker-compose.yml` too deeply; it must be directly inside the top-level folder.

Example of an accepted layout:

```text
my-submission.zip
└── my-submission/
    ├── docker-compose.yml
    ├── src/
    ├── Dockerfile (optional)
    └── README.md
```

Notes:

- macOS may add `__MACOSX/` entries; these are ignored.
- Keep the ZIP under the size limit specified in the contest instructions (default: 50 MB).

## Docker Compose: reliable service startup

- Use `ports:` to expose the port on which the app listens. The evaluator may remap the host-side port.
- Declare dependent services, such as databases and caches, in the same `docker-compose.yml`.
- The evaluator waits up to 90 seconds for `GET /health` to become healthy; aim for a faster startup.
- Add readiness logic: do not return HTTP 200 from `/health` until startup work, such as database migrations, is complete.
- If the app seeds data at startup, ensure seeding finishes before `/health` returns HTTP 200.

## Required runtime behavior

### Health endpoint

- `GET /health` must return HTTP 200 without authentication.
- The response body can be any valid JSON, for example `{"status":"ok"}`.

### Problem-specific endpoints (Karate)

- The supplied `.feature` file is the contract. Implement exactly what its assertions expect.
- Karate checks response equality; missing fields, unexpected fields, or incorrect values can fail a scenario.
- Do not require participants to upload files unless the problem instructions say to. If an image or other asset is bundled with the problem, read it from the expected path.
- If `docker-compose.yml` passes API keys or other configuration to the container, the application must read those settings from within the container.

## How evaluation runs

1. The submission is accepted and queued; the UI shows a job ID.
2. The evaluator extracts the ZIP into a versioned folder and runs `docker compose up --build`.
3. It polls `GET /health` until the endpoint returns HTTP 200 or the 90-second timeout is reached.
4. Karate runs the supplied `.feature` file against the running service.
5. The evaluator writes a report and computes the score as `(scenarios passed / total scenarios) × 100`.
6. The UI provides `evaluation-result.json` and an interactive Karate HTML report for download.

Use the Karate HTML report or `evaluation-result.json` to see which assertions failed and why. Each scenario is a scoring unit: the final score is the percentage of Karate scenarios that passed. A scenario passes only when every assertion succeeds and the expected HTTP status code matches.

The health check and Docker startup gates must succeed for testing to begin, but they do not count as scored scenarios.

## Debugging common failures

- **`docker compose up` fails:** Check `docker-compose.yml` syntax and build context; run locally and fix build errors first.
- **`/health` never returns 200:** Ensure startup tasks, such as migrations and seeding, finish before reporting healthy.
- **Karate scenario fails:** Open the Karate HTML report to see the failing step, expected value, and actual response. Fix the response shape or status code.

## Submission checklist

- [ ] ZIP contains exactly one top-level folder.
- [ ] `docker-compose.yml` is directly inside that folder.
- [ ] `GET /health` returns HTTP 200 as soon as the app is ready; heavy initialization does not run inside `/health`.
- [ ] Endpoints asserted in the Karate `.feature` file are implemented and return the exact expected shapes.
- [ ] Required assets and seed data are bundled where the application expects them.
- [ ] ZIP size is below the applicable limit.

## FAQs

**My feature file asserts exact JSON and my service returns extra fields. Will it fail?**  
Yes. Karate deep-equality checks can fail when extra fields are present. Return only the fields the feature expects, unless the problem instructions allow otherwise.

**Can I change the feature file?**  
No. The feature file distributed with the problem is the evaluation contract.

**Where can I see detailed failures?**  
Open **View Karate Test Report** in the UI for per-scenario failures, request/response artifacts, and assertion diffs. You can also open `evaluation-result.json` from the UI to see what happened during evaluation.
