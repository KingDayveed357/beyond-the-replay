# Azure setup guide: hosting on Azure Container Apps, Claude on Microsoft Foundry

This guide takes Beyond the Replay from your laptop to a reliable public URL on Azure, and
optionally moves the AI agents onto Claude in Microsoft Foundry. Do the parts in order. Part B
(hosting) matters most for the hackathon; Part C (Foundry) is optional.

> **Money first.** Hosting can be close to free; AI calls cost money wherever they run.
> - **Zero-spend setup:** host on Container Apps with **no AI key**. Every showcase match still has
>   its saved AI investigation and all 100 recaps; judges can add their own key in the Model menu.
> - **Claude on Foundry is billed through Azure** (Microsoft Marketplace) at the same per-token
>   prices as the Claude API. It does not make AI free. Free-trial credits may not cover Marketplace
>   models, so check before you rely on them.
> - Set an **Azure budget alert** (step B9) before anything else goes live.

---

## Part A: Get an Azure subscription

1. **Azure for Students** (no card, if you have a school email at an eligible institution):
   https://azure.microsoft.com/free/students. Check that your country and institution are eligible.
2. **Azure free account** (needs a card for identity checks; includes trial credit and some always-free services):
   https://azure.microsoft.com/free.
3. Whatever you use, note your **subscription name** in the portal (https://portal.azure.com → Subscriptions).

If neither works before the deadline, use the free fallback host in `docs/DEPLOYMENT.md` (option B)
and say in the submission that the app is "Azure Container Apps-ready" with this guide included.

---

## Part B: Host the app on Azure Container Apps

### B1. Install the tools (once)

```powershell
winget install --exact --id Microsoft.AzureCLI
```

Close and reopen your terminal, then:

```bash
az login
az account set --subscription "<your subscription name>"
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

### B2. Publish the container image (free, via GitHub)

1. Create a **public** GitHub repository and push this folder (the hackathon requires a public repo anyway).
2. The included workflow (`.github/workflows/ci.yml`) runs all tests, builds the image and pushes it to
   GitHub Container Registry as `ghcr.io/<owner>/<repo>:latest` and `:<commit sha>`.
3. On GitHub: your profile → **Packages** → the package → **Package settings** → **Change visibility → Public**.
   A public image means Azure can pull it without a registry password, and you avoid paying for
   Azure Container Registry.
4. Copy the commit SHA of the build you want (from the Actions run). Pinning a SHA (instead of
   `latest`) makes deployments repeatable and easy to roll back.

> Lowercase: registry paths must be lowercase. The workflow lowercases `<owner>/<repo>` for you; use
> the lowercase form in the commands below.

### B3. Create the Container Apps environment and the app

Pick one region and use it everywhere (for example `westeurope`; any region where Container Apps
is available works).

```bash
az group create --name btr-rg --location westeurope

az containerapp env create --name btr-env --resource-group btr-rg --location westeurope

az containerapp create \
  --name beyond-the-replay \
  --resource-group btr-rg \
  --environment btr-env \
  --image ghcr.io/<owner>/<repo>:<commit sha> \
  --target-port 8000 \
  --ingress external \
  --cpu 0.25 --memory 0.5Gi \
  --min-replicas 0 --max-replicas 1
```

PowerShell users: replace each trailing `\` with a backtick `` ` ``, or put the command on one line.

Get your public URL:

```bash
az containerapp show --name beyond-the-replay --resource-group btr-rg --query properties.configuration.ingress.fqdn -o tsv
```

Why these settings:
- **0.25 vCPU / 0.5 GiB** is the smallest size and enough for this app (the data and caches are small).
- **max-replicas 1**: the AI spend ledger, the per-visitor rate limits and the live ingestion feeds live in the
  app's memory. With more than one replica, a viewer could land on a replica that doesn't hold their feed.
- **min-replicas 0** scales to zero while nobody is visiting (cheapest; the first visit takes several
  seconds to wake up). Switch to 1 for the judging window (B8).

### B3b. App settings (always)

```bash
az containerapp update --name beyond-the-replay --resource-group btr-rg --set-env-vars   BTR_NAMES=fictional BTR_PUBLIC_URL=https://<your fqdn>
```

`BTR_NAMES=fictional` is already the default; setting it explicitly documents that the public app shows no
real clubs or players. `BTR_PUBLIC_URL` makes the A2A agent card advertise the right address. Then check:
`https://<your fqdn>/a2a/.well-known/agent-card.json` and `https://<your fqdn>/studio` (press *Kick off a new
synthetic match*).

### B4. Configure AI (choose one)

**Zero spend (recommended while money is tight):** do nothing. Without a key the app serves saved AI
results, recaps, the statistics-only investigation, and bring-your-own-key.

**With your Anthropic key, capped:**

```bash
az containerapp secret set --name beyond-the-replay --resource-group btr-rg --secrets anthropic-key=<your key>
az containerapp update --name beyond-the-replay --resource-group btr-rg \
  --set-env-vars ANTHROPIC_API_KEY=secretref:anthropic-key BTR_SERVER_BUDGET_USD=0.20 BTR_FRESH_RUNS_PER_HOUR=2
```

The key is stored as a Container Apps secret and never appears in logs, responses or the browser.
**Also set a monthly spend limit in the Anthropic Console** (Settings → Limits). It is the only
hard limit: the app's cap is an estimate and restarts from zero when the container restarts.

**With Claude on Microsoft Foundry:** see Part C.

### B5. Health probes

Portal → your Container App → **Containers** → **Edit and deploy** → select the container →
**Health probes**:
- **Liveness:** HTTP GET, path `/api/health`, port `8000`, initial delay 10 s, period 30 s.
- **Readiness:** HTTP GET, path `/api/health`, port `8000`, initial delay 5 s, period 10 s.

Save to create a new revision. Azure then restarts the container if it ever stops responding.

### B6. Smoke test (free: never calls the model)

```bash
python scripts/smoke_test.py https://<your fqdn>
```

All checks must pass, especially **"saved AI investigation (prevents paid runs)"** for every match.
If that check fails, visitors opening that match would trigger a paid AI run. Fix it before sharing
the URL (usually it means the deployed image is older or newer than the saved results).

Then open the URL in a private window and click through: landing → investigation → reveal →
"Watch … live" (let it play) → change language → accuracy page.

### B7. Logs

```bash
az containerapp logs show --name beyond-the-replay --resource-group btr-rg --follow
```

Each investigation logs one line with its id, mode, whether it was a saved result, and the estimated
cost. Keys are redacted by the app's log filter.

### B8. Judging window (27 Oct to 10 Nov)

Keep the app warm so judges never wait for a cold start, and keep exactly one replica:

```bash
az containerapp update --name beyond-the-replay --resource-group btr-rg --min-replicas 1 --max-replicas 1
```

After judging, go back to `--min-replicas 0` (or delete the resource group: `az group delete --name btr-rg`).
The rules require the project to stay available free of charge until the end of judging.

### B9. Budget alert (do this first, it takes two minutes)

Portal → **Cost Management + Billing** → **Budgets** → **Add**: scope your subscription, amount
for example $5 per month, alerts at 50% and 90% to your email. Check pricing for your size and
region in the Azure pricing calculator (https://azure.microsoft.com/pricing/calculator); Container
Apps' consumption plan includes a monthly free grant, and an always-on replica uses part of it.

### B10. Updating and rolling back

Push to `main` → CI builds a new image tagged with the commit SHA → deploy it:

```bash
az containerapp update --name beyond-the-replay --resource-group btr-rg --image ghcr.io/<owner>/<repo>:<new sha>
```

To roll back, run the same command with the previous SHA. Rerun the smoke test after every deploy.

---

## Part C: Claude on Microsoft Foundry (optional)

The app already supports it: setting `BTR_PROVIDER=foundry` sends the **server key's** AI requests to
your Foundry deployment through the Anthropic SDK's `AnthropicFoundry` client. Bring-your-own-key
keeps using the Claude API. Nothing else changes.

### C1. Check before you start

- **Eligibility:** Claude models in Foundry are third-party Marketplace offers. Some subscription types
  (free trials, student or sponsorship offers) may not be able to deploy them. If deployment is
  blocked, keep hosting on Azure and use the zero-spend setup.
- **Model availability:** look for **Claude Haiku 5.5** in the catalogue. The saved AI results were made
  with Haiku 5.5. If you deploy a different model (for example Claude Haiku 4.5), the app will not find
  saved results for it and **every investigation page would trigger a paid run at a higher price**.
  Only switch to Foundry if Haiku 5.5 is available.
- **Region:** Claude is offered in a limited set of regions; the catalogue shows which.

### C2. Create the Foundry resource and project

1. Go to https://ai.azure.com and sign in with your Azure account.
2. **Create project**. It creates a Foundry resource. Choose a region where the Claude model you need
   is available. Note the **resource name**.

### C3. Deploy the model

1. In your project: **Model catalog** → filter by publisher **Anthropic** → open **Claude Haiku 5.5**.
2. **Deploy**. Accept the offer terms if asked (this is where Marketplace billing starts).
3. Set the **deployment name** to `claude-haiku-5-5` (the app's model id), so no extra setting is
   needed. If you choose another name, set `BTR_FOUNDRY_DEPLOYMENT` to it.
4. **Lower the deployment's rate limit** (tokens per minute) to a small value. It is a second spending guard.

### C4. Get the key and endpoint

On the deployment page, copy the **key** and check the endpoint. It should look like
`https://<resource name>.services.ai.azure.com/anthropic/`. The resource name is the part before
`.services.ai.azure.com`.

### C5. Configure the app

```bash
az containerapp secret set --name beyond-the-replay --resource-group btr-rg --secrets foundry-key=<your Foundry key>
az containerapp update --name beyond-the-replay --resource-group btr-rg --set-env-vars \
  BTR_PROVIDER=foundry \
  ANTHROPIC_FOUNDRY_RESOURCE=<resource name> \
  ANTHROPIC_FOUNDRY_API_KEY=secretref:foundry-key \
  BTR_SERVER_BUDGET_USD=0.20 BTR_FRESH_RUNS_PER_HOUR=2
```

Locally, the same variables go in `.env` (see `.env.example`).

### C6. Verify

1. `python scripts/smoke_test.py https://<your fqdn>`: provider status should show `platform: foundry`
   and `key configured: True`. This still makes no model calls.
2. One deliberate live check (costs about half a US cent with Haiku 5.5): open a match and press
   **Run fresh** once. It should finish in about 30 to 60 seconds with "AI agents · Claude Haiku 5.5".
   If it fails, the error message names the cause (key rejected, model not available, rate limited).
3. In the submission, list **Microsoft Foundry** only after this check succeeds.

---

## Part D: Production readiness checklist

| Item | Status in the code | Your action |
|---|---|---|
| HTTPS | Container Apps ingress provides it | none |
| Secrets | Read from environment; never logged, returned or sent to the browser | store keys as Container Apps secrets |
| Per-visitor rate limits behind Azure's proxy | Container runs uvicorn with `--proxy-headers` | none |
| Live stream across proxy time limits | Match centre reopens the feed from the current minute if the connection drops | none |
| Health checks | `/api/health` | add probes (B5) |
| Cold starts | Scale-to-zero by default | `--min-replicas 1` during judging (B8) |
| Spend | App cap (estimate) + saved results + no-key mode | Anthropic Console or Foundry limit + Azure budget alert |
| Saved results match the deployed code | Smoke test checks every match | run it after every deploy (B6) |
| Rollback | Images tagged by commit | redeploy the previous SHA (B10) |
| Logs | Structured lines to stdout; keys redacted | `az containerapp logs show --follow` |
| Tests | 80+ tests in CI, no network calls | keep CI green before deploying |

## Part E: Before you submit

- [ ] Public GitHub repo; CI green; image public on GitHub Container Registry.
- [ ] App URL works in a private window from your phone too.
- [ ] Smoke test passes against the live URL.
- [ ] `--min-replicas 1` set for the judging window.
- [ ] Budget alert set; Anthropic/Foundry limit set (or no key configured).
- [ ] Demo video (under 2 minutes) uploaded; links filled into `docs/SUBMISSION.md`.
- [ ] Submission lists only technologies actually in use (Container Apps only if deployed there; Foundry only if C6 passed).
