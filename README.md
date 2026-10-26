# Beyond the Replay

**Explainable match intelligence that can prove what it says.** Synthetic match events stream in as they
happen; a Microsoft Agent Framework pipeline turns every batch into live stats, key moments that say why they
matter, storylines that build over the match, broadcast overlays and studio-ready recaps, personalised for
every fan in five languages. For decisive goals, a multi-agent investigation (investigator, sceptic, code
verifier, producer) works out the real cause, and a published benchmark scores it against an answer key the
AI never sees.

> **Simulated matches, fictional names.** Team strengths are modelled on a real top-flight season, but every
> club, player, stadium and official shown is fictional (`server/identity.py`), and every event is generated
> by the simulation. No crests, badges, photos or footage are used.

Built for the Microsoft × Premier League *Inside the Game* hackathon (challenge: *The Synthetic Match Insights
Engine for Premier League Studio*).

## One pipeline, five stages

| Stage | In the product |
|---|---|
| **Ingest** | `POST /api/feeds` opens a live feed (guide: [`docs/API.md`](docs/API.md), interactive reference at `/docs`, example match: [`samples/match-feed.json`](samples/match-feed.json)); a data provider pushes events in batches with a per-feed write token (`/api/schema` is the JSON Schema contract). Every event is validated (schema, roster, pitch bounds, clock order); rejects come back with a reason. The **Live Studio** kicks off a brand-new synthetic match through this path, and `scripts/feed_simulator.py` does the same over HTTP against any deployment. |
| **Interpret** | Per-minute states: score, possession, shots, expected goals, pass accuracy, **pass difficulty** (trained model), pass distance, territory, pressing (PPDA), a control index, **chaos**, tempo, **momentum**, player speed and distance carried. |
| **Explain** | Key moments with *why they matter*. **Storylines** open and develop as patterns build (a side on top, attacks down one flank and the defender facing them, a defender losing duels late, a booked player still fouling, a side chasing the game), plus milestones and a "story so far" every 15 minutes. For the decisive goal, the **agent investigation** explains the cause and what it wasn't. |
| **Render** | Broadcast match centre with score bug, lower thirds and speed/distance name tags; a versioned **JSON overlay track** and **WebVTT** metadata track; the **Studio Pack**: 30- and 60-second presenter scripts with graphics cues, a highlights rundown with timecodes (**CMX3600 EDL** and CSV for editing suites), lower thirds, social copy, push alerts and stat cards. |
| **Personalise** | Five languages (English, Spanish, French, Brazilian Portuguese, Arabic right to left), favourite club, **follow a player** all match, fan or analyst depth, one-number focus, **spoiler-free** mode, and club- or player-framed studio packs with "for you" alerts. Claude writes half-time and full-time recaps per audience and language, fact-checked before they are shown. |

## Agents and orchestration (Microsoft Agent Framework)

Two Agent Framework workflows run the product (`GET /api/agents`, `GET /api/pipeline`):

```
goal investigation   intake ─► investigator ─► sceptic ─► verifier (code) ─► producer ─► publish
                                     └──(sceptic off)──────┘
match pipeline       ingest ─► interpret ─► explain ─┬─► render ──┬─► publish
                                                     └─► narrate ─┘     (fan-out / fan-in)
```

- **Distinct roles over shared state.** The investigator (Claude Haiku 5.5 with read-only match tools, or
  change-point statistics) proposes causes onto a shared evidence board; the sceptic tries to break each one
  (the booking is always tested); a code verifier keeps only claims backed by the events they cite; the
  producer writes only what survived, and its text must pass a fact check or a labelled template is used.
- **Failure recovery.** If a Claude role times out, is rate-limited or returns malformed output, its
  deterministic counterpart takes over and the result records the hand-over (`orchestration.recovered`).
  Errors only the user can fix (a rejected key) still surface.
- **A2A.** The match analyst is exposed over the Agent2Agent protocol through `agent_framework_a2a`
  (`/a2a/.well-known/agent-card.json`): other agents can ask why a goal happened, for storylines or for a
  presenter script, at no model cost.
- **MCP.** `python -m mcp_server` exposes match state, moments, players, why-goal and overlays as tools for
  GitHub Copilot agent mode (`.vscode/mcp.json`) or any MCP client.

## Why it is different

AI can explain anything; convincing is not the same as correct. Each simulated match has a hidden cause planted
in it, and its effect is **measured** by re-playing the match 120 times from that moment with and without it.
That answer key is never reachable by the agents, so every explanation can be scored, and the results are
published in the app, misses included.

| On 59 new matches with a clear cause (one run each) | Right cause first | In top 3 | Claims not backed by data |
|---|---|---|---|
| AI agents (Claude Haiku 5.5 + tools + sceptic + verifier) | 75% | 83% | 1.8% proposed, all caught; 0% shown |
| Statistics only | 78% | 98% | 0% |
| Claude reading the raw match log (no tools, no checks) | 20% | 41% | 69% |

## Run it

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt     # Python 3.12+
cd web && npm install && npm run build && cd ..
.venv/Scripts/python -m uvicorn server.app:app --port 8000                 # http://localhost:8000
.venv/Scripts/python -m unittest tests.test_phase0 tests.test_workflow tests.test_api tests.test_llm tests.test_analytics tests.test_mcp tests.test_identity tests.test_feeds tests.test_a2a
python scripts/feed_simulator.py http://localhost:8000 --speed 30         # stream a new match into a live feed
python scripts/smoke_test.py http://localhost:8000                          # post-deploy check, never calls a model
```

No key is needed: the app serves saved AI investigations and recaps, the statistics-only investigation,
ingestion, storylines and studio packs; judges can add their own Anthropic key in the Model menu. On Python
3.13+ without a C compiler, install PyYAML first with `PYYAML_FORCE_LIBYAML=0 pip install pyyaml --no-binary pyyaml`.
Deployment (Azure Container Apps, optional Claude on Microsoft Foundry): `docs/AZURE_SETUP.md`.

## Production readiness

Server-side keys only (never in the browser or logs, with a redaction filter); bring-your-own-key held in
memory per request; saved results keyed to the exact prompts and tools; estimated-spend cap and per-visitor
limits; per-feed write tokens, batch and feed limits, expiry; structured errors; a health endpoint; CI on every
push publishing an image to GitHub Container Registry; a smoke test that checks a deployment end to end
without calling a model; and a compliance test that scans every public output for real names.

## Repository map

| Path | What |
|---|---|
| `phase0/` | Seeded match engine (real squad strengths, hidden causes, paired re-runs) and the answer key |
| `analytics/` | Live states, xG and pass-difficulty models, moments, overlay cues, `narrative.py` (storylines), `studio_pack.py`, recaps, five-language text |
| `investigation/` | Evidence board, sceptic, verifier, producer, fact check; `orchestration.py` (Agent Framework workflow); `llm/` (Claude agents, provider, tools) |
| `server/` | FastAPI app; `feeds.py` (ingestion + Agent Framework match pipeline); `identity.py` (fictional names); `a2a_agent.py`; `provider_sim.py` |
| `schemas/` | `match-feed.schema.json`, the ingestion contract |
| `mcp_server/` | MCP tools for Copilot or any agent |
| `web/` | React + TypeScript: landing, match centre, Live Studio, Studio Pack, investigation, benchmark |
| `scripts/` | League pack, showcase matches, pass model, saved results, feed simulator, smoke test |
| `docs/` | Azure setup, deployment, design system, demo script, submission text |

## Data

Team and player strengths are calibrated from public statistics for a real season (`scripts/build_league.py`;
raw files not redistributed). Everything users see is fictional by default (`BTR_NAMES=fictional`); the real
names stay internal so the calibration and saved results keep working. Events and explanations are simulated.
