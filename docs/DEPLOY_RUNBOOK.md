# Deployment runbook: Azure Container Apps on a student budget

The shortest safe path from this repository to a public URL judges can use, checked against the code on
2026-10-26. It assumes **Azure for Students** ($100 credit) and **no AI key on the server**. Do the phases in
order; each ends with a check. Background and options: `docs/AZURE_SETUP.md`.

## What we verified before writing this

| Question | Finding |
|---|---|
| Does one image serve everything on port 8000? | Yes. The Dockerfile builds the React app (stage 1) and copies it to `web/dist`; FastAPI serves `/api/*`, `/a2a/*` (agent card at `/a2a/.well-known/agent-card.json`), `/docs`, and every other path (`/`, `/studio`, `/live/…`, `/feedback`) as the React app. Uvicorn listens on `$PORT` (default 8000) with `--proxy-headers`. A local run returned 200 for `/`, `/studio`, `/live/m300121`, `/feedback` and `/docs`. |
| Is 0.25 vCPU / 0.5 GiB enough? | Yes. Measured memory: 141 MB after warming all 5 matches in 5 languages plus studio packs; 179 MB holding the maximum 24 complete live feeds (about 2 MB each). Startup is about 3.3 s of imports on a laptop; the image precompiles Python bytecode, so expect roughly 10–30 s cold start on a quarter vCPU, plus the first image pull. |
| Does the code run on the image's Python (3.12)? | Yes: `vermin` reports no 3.13+ syntax, and CI runs the full test suite on 3.12. |
| Does the CI publish a reproducible image? | Yes. On every push to `main`, after tests pass, it pushes `ghcr.io/kingdayveed357/beyond-the-replay:latest` and `:<full commit SHA>`, labelled with the repository and revision. **Deploy the SHA tag**, never `latest`. |
| Without an AI key, do judges still see AI results? | Yes. Saved investigations (5 matches) and 100 recaps are in the image; the smoke test checks each one is served from the saved file. "Run fresh" is refused without a key (no spend). The top bar shows "Saved AI results". |
| CORS? | Not needed: the app and API share one origin. The CORS allowance is only for the local Vite dev server. A2A calls are server-to-server. |
| Secrets? | None in this setup. `.env` is excluded from the image (`.dockerignore`) and from git (`.gitignore`). |

**What does not survive a restart or scale-to-zero** (all held in memory or on the container's own disk):
live ingestion feeds (the Studio now says so and offers a new match instead of retrying), the per-visitor rate
limits, and feedback notes written to the local file. Saved AI results and recaps are in the image and always
survive. If feedback starts arriving and matters, add Table Storage later (`docs/AZURE_SETUP.md`, step B4b,
about $0.10 a month). Foundry is not part of this plan: student subscriptions generally cannot buy
third-party Marketplace models, and credits may not cover them.

## Phase 0: before Azure (GitHub, 10 minutes)

1. Commit and push everything to `main`, including the new folders `schemas/`, `samples/`, and the new files in
   `server/`, `tests/` and `web/src/`. Check that `.env` is **not** in the commit (`git status` must not list it).
2. Make the repository **public** (Settings → General → Danger zone → Change visibility).
3. Watch **Actions** → the `ci` run. Both jobs (`test`, `image`) must be green. Copy the full commit SHA of
   that run (the 40-character id).
4. Make the image public: your GitHub profile → **Packages** → `beyond-the-replay` → **Package settings** →
   **Change visibility → Public**. (Azure then pulls it without a password, and you pay nothing for a registry.)

**Check:** open `https://github.com/KingDayveed357/beyond-the-replay/pkgs/container/beyond-the-replay` in a private
window; it must load and list the SHA tag.

## Phase 1: guard the credit (Azure portal, 3 minutes)

Portal → **Cost Management + Billing** → **Budgets** → **Add**. Scope: your Azure for Students subscription.
Amount **$20**, monthly. Alerts at **50 %** and **90 %** to your email. (This only warns; Azure for Students
also stops services rather than charging a card when the $100 runs out.)

## Phase 2: create the app (portal, 10 minutes)

Portal search bar → **Container Apps** → **Create** → **Container App**.

**Basics**
- Subscription: Azure for Students. Resource group: **Create new** → `btr-rg`.
- Container app name: `beyond-the-replay`. Region: **West Europe** (if refused with "disallowed by policy",
  pick another allowed region, e.g. North Europe or East US, and use it everywhere).
- Container Apps environment: **Create new** → name `btr-env`, plan **Consumption only**, zone redundancy
  **Disabled**. On its **Monitoring** tab choose **Don't save logs** (no Log Analytics charges; live log
  streaming still works).

**Container**
- Untick *Use quickstart image*. Image source: **Docker Hub or other registries**. Image type: **Public**.
- Registry login server: `ghcr.io`. Image and tag: `kingdayveed357/beyond-the-replay:<commit SHA>`.
- CPU and memory: **0.25 CPU cores, 0.5 Gi memory**.
- Environment variables: `BTR_NAMES` = `fictional`. (No `ANTHROPIC_API_KEY`.)

**Ingress**
- Ingress **Enabled**, traffic **Accepting traffic from anywhere**, ingress type **HTTP**,
  target port **8000**. Leave transport on Auto.

**Review + create** → **Create**. Takes 2–5 minutes.

## Phase 3: finish configuration (portal, 5 minutes)

1. **Scale** (app → Application → Scale): min replicas **0**, max replicas **1** → Save. Max 1 is required:
   live feeds and rate limits live in one process's memory.
2. Copy the **Application Url** from the Overview page, e.g. `https://beyond-the-replay.<random>.westeurope.azurecontainerapps.io`.
3. **Environment variables** (app → Application → Containers → Edit and deploy → container → Environment
   variables): add `BTR_PUBLIC_URL` = that URL (no trailing slash). This makes the A2A agent card advertise
   the right address. Create the new revision.
4. **Health probes** (same Edit and deploy screen → Health probes):
   - Startup: HTTP GET `/api/health`, port 8000, period 5 s, failure threshold 12 (allows a 60 s cold start).
   - Liveness: HTTP GET `/api/health`, port 8000, period 30 s.
   - Readiness: HTTP GET `/api/health`, port 8000, period 10 s.

## Phase 4: verify (your terminal, 5 minutes)

```powershell
.venv\Scripts\python scripts\smoke_test.py https://<your app url>
```

Every line must say `ok`, especially *saved AI investigation (prevents paid runs)* for all 5 matches,
*fictional names by default*, *live ingestion* and *A2A agent card*. Then click through in a private browser
window, including on your phone: landing → investigation (make your call, reveal) → match centre (kick off,
sound on) → Live Studio (kick off a new match) → Studio pack → Feedback.

To watch the server while you click: app → **Monitoring → Log stream**.

## Phase 5: availability during judging

The rules require the project to be **"available free of charge and without any restriction for testing"**
until judging ends (10 Nov, 23:59 PT); judges "are not required to test" and may judge from the video and text.
So public access is required, not an uptime guarantee. But a judge who meets a 30-second blank page may
not wait.

| Period | Min replicas | Why |
|---|---|---|
| Now until you submit | **0** | You are the only visitor. Cold starts are fine. |
| While recording the video | **1** (set it 10 minutes before) | No cold start on camera. |
| Submission (27 Oct) to 10 Nov 23:59 PT | **1** | Judges get an instant page. |
| After 10 Nov | **0**, or delete `btr-rg` | Stop all charges. |

Set it from the portal (Scale) or:

```powershell
az containerapp update --name beyond-the-replay --resource-group btr-rg --min-replicas 1 --max-replicas 1
```

**Estimated cost** (Consumption plan, list prices; check the [pricing page](https://azure.microsoft.com/pricing/details/container-apps/)):
a replica that is mostly idle is billed at the idle rate after the monthly free grant (180,000 vCPU-seconds and
360,000 GiB-seconds per subscription). One 0.25 vCPU / 0.5 GiB replica running all of 27 Oct–10 Nov comes to
roughly **$1–3 in total**. No registry, no Log Analytics, no AI key. Your $100 is not at risk; the budget alert is
the safety net.

## Updating and rolling back

Push to `main` → wait for green CI → app → Containers → Edit and deploy → change the image tag to the new
SHA → Create. Rolling back is the same with the previous SHA. Rerun the smoke test after every change.
Avoid deploying new features during judging.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Revision stuck "Provisioning", image pull error | Package still private (Phase 0 step 4), or a typo in the image name (must be lowercase). |
| "Disallowed by policy" on create | Region not allowed for student subscriptions: pick another. |
| Page loads after 20–40 s, then fine | Cold start with min replicas 0. Expected; set 1 for judging. |
| Smoke test: saved AI investigation FAIL | The image is older or newer than the saved results. Deploy the SHA whose CI passed. Never fix this by adding a key. |
| Live Studio says the feed ended | The replica restarted (scale to zero, redeploy). Kick off a new match. |
| A2A card shows `localhost` | `BTR_PUBLIC_URL` not set (Phase 3 step 3). |
