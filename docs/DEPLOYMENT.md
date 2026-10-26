# Deployment and model configuration

> Step-by-step Azure guide (Container Apps hosting and Microsoft Foundry): **docs/AZURE_SETUP.md**.

One container serves everything: API, live event streams (server-sent events), live ingestion feeds, overlay
and studio-pack export, the A2A endpoint and the built frontend. Live feeds are held in memory, so run exactly
one replica. Inference runs **server-side only**; the browser never receives the server's
key and the frontend has no build-time secrets. A local `.env` is for development only.

## Option A: Azure Container Apps (preferred for the hackathon)

Needs an Azure subscription (Azure for Students works without a card if you are eligible) and the
Azure CLI. From the repository root:

```bash
az login
az group create --name btr-rg --location westeurope
az containerapp up --name beyond-the-replay --resource-group btr-rg --source . --ingress external --target-port 8000
az containerapp secret set --name beyond-the-replay --resource-group btr-rg --secrets anthropic-key=<your key>
az containerapp update --name beyond-the-replay --resource-group btr-rg --set-env-vars ANTHROPIC_API_KEY=secretref:anthropic-key
```

`az containerapp up --source .` builds the Dockerfile in Azure Container Registry and deploys it with
HTTPS ingress. Keep **min replicas at 1** during judging so the first visit is not a cold start:
`az containerapp update -n beyond-the-replay -g btr-rg --min-replicas 1 --max-replicas 2`.

### Claude through Microsoft Foundry (optional, same code path)

Claude models are available in Microsoft Foundry, billed through Azure at the same per-token
prices. Once a Foundry deployment exists, the provider can be pointed at it with the Anthropic
SDK's `AnthropicFoundry` client; nothing else in the pipeline changes. This is not wired up yet
because no Azure account was available while building.

## Option B: a free container host (no Azure)

Any host that runs a Dockerfile and supports long-lived HTTP responses works. For example, a
Hugging Face Space with the Docker SDK (free CPU tier): create a Space, push this repository to it,
add `ANTHROPIC_API_KEY` as a Space secret, and set `PORT=7860` as a variable (Spaces route to 7860).
The Dockerfile already listens on `$PORT`.

## Option C: run the published image

On every push to `main`, GitHub Actions runs the tests and publishes
`ghcr.io/<owner>/<repo>:latest` to GitHub Container Registry. Any host can run it:

```bash
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=<your key> ghcr.io/<owner>/<repo>:latest
```

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | for the demo key | none | Server key. Without it the app still serves saved AI results, recaps, the statistics-only investigation, and bring-your-own-key. |
| `PORT` | no | `8000` | Port the container listens on. |
| `BTR_MODEL` | no | `claude-haiku-5-5` | Model for the server key (allow-listed). |
| `BTR_SERVER_BUDGET_USD` | no | `0.20` | Cap on *estimated* server-key spend; fresh runs stop at the cap. |
| `BTR_FRESH_RUNS_PER_HOUR` | no | `2` | Fresh server-key AI runs per visitor IP per hour. Saved results are unlimited. |
| `BTR_MAX_CONCURRENT` | no | `2` | AI investigations running at once (server key and BYOK combined). |
| `BTR_RUNTIME` | no | `/tmp/btr-runtime` in the container | Spend ledger location. Mount a volume to keep it across restarts. |
| `BTR_PROVIDER` | no | `anthropic` | `foundry` sends server-key requests to Claude on Microsoft Foundry (see `docs/AZURE_SETUP.md`). BYOK always uses the Claude API. |
| `ANTHROPIC_FOUNDRY_RESOURCE` | with Foundry | none | Foundry resource name (`https://<name>.services.ai.azure.com/anthropic/`). |
| `ANTHROPIC_FOUNDRY_API_KEY` | with Foundry | none | Foundry key. Store it as a secret. |
| `BTR_FOUNDRY_DEPLOYMENT` | no | the model id | Foundry deployment name, if you did not name it after the model. |
| `BTR_NAMES` | no | `fictional` | Names shown in every public output. `fictional` (broadcast-safe, no third-party trademarks) or `real` for local calibration work. |
| `BTR_PUBLIC_URL` | for A2A | `http://localhost:8000` | The app's public URL, written into the A2A agent card (`/a2a/.well-known/agent-card.json`). |
| `BTR_FEEDBACK_CONNECTION` | recommended | none | Azure Storage connection string (store as a secret). Feedback goes to Table Storage; without it, to a file that a restart wipes. |
| `BTR_FEEDBACK_PER_HOUR` | no | `6` | Feedback notes accepted per visitor address per hour. |
| `BTR_DEMO_FEEDS_PER_HOUR` | no | `12` | Live Studio demo matches a visitor can start per hour. |
| `BTR_IDENTITY` | no | `pl` | Engine calibration: `fictional` generates matches from invented squads instead of real season strengths. |

## Cost controls

**Zero-spend deployment:** leave `ANTHROPIC_API_KEY` unset. Every showcase match still has its saved AI
investigation and all recaps; the statistics-only investigation works; judges can use their own key.

**If you do set a key,** use three guards together:
1. An organisation **spend limit in the Anthropic Console**. This is the only hard limit; the app's cap is an estimate.
2. `BTR_SERVER_BUDGET_USD` (default $0.20) and `BTR_FRESH_RUNS_PER_HOUR` (default 2).
3. A persistent volume for `BTR_RUNTIME`. Without one, a container restart resets the app's spend ledger to zero.

- Saved results first: showcase matches ship with saved AI investigations and 100 recaps (5 languages).
- Bounded agents (8 turns each), explicit token limits, SDK retries capped at 2 with backoff.
- Spend is reported per run from provider token counts (estimates from list prices; Anthropic billing is authoritative).
- Provider failures are shown, never hidden: retry, the statistics-only version, or bring-your-own-key.

## Bring your own key (BYOK)

The key is held in browser memory only, sent per request as `X-BYOK-Key` to this server, used for
that request and discarded: never stored, logged, cached or returned. BYOK runs are fresh, not
cached, not counted against the demo budget, and limited by the same concurrency cap.

## MCP server

`python -m mcp_server` exposes the match intelligence as read-only MCP tools (list matches, match
state at a minute, key moments in five languages, player summary, why a goal happened, overlay
track). `.vscode/mcp.json` registers it for GitHub Copilot agent mode in VS Code.
