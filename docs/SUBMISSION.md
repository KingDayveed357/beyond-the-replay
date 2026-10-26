# Submission text

> Paste into the project page (or the manual submission email). Fill in the three bracketed links. Name only
> technologies that are live in the version you submit: keep the Azure lines only once the app runs there.

## Title (max 140)
Beyond the Replay: explainable match intelligence that proves what it says

## Tagline (max 300)
Synthetic events in, trusted football stories out. A Microsoft Agent Framework pipeline turns live match events
into stats, storylines, broadcast overlays and studio-ready recaps for every fan in five languages, and AI agents
explain decisive goals with every claim checked and accuracy published.

## Keywords
Microsoft Agent Framework, Multi-agent, A2A, MCP, GitHub Copilot, Azure Container Apps, Explainable AI, Real-time, Broadcast, Personalisation, Synthetic data

## Challenge
The Synthetic Match Insights Engine for Premier League Studio

## Category
Best Multi-Agent System (also eligible for the Grand Prize).

## Description

**The problem.** A broadcast or streaming team gets thousands of events per match and minutes to turn them
into stories, graphics and recaps for audiences who want very different things, in different languages. AI can
write those stories, but it can also confidently explain things that never happened.

**What we built.** One pipeline, five stages, exactly as the brief describes:

1. **Ingest.** A data provider opens a live feed and pushes synthetic events as they happen (passes, carries,
   dribbles, crosses, shots, tackles, interceptions, clearances, fouls, cards, possession, pressure, speeds,
   match metadata). Each event is validated against a published JSON Schema; rejects come back with a reason.
   The Live Studio kicks off a never-seen synthetic match through this exact path, so judges can watch it work.
2. **Interpret.** Per-minute match state: xG, pass difficulty (trained model) and distance, territory,
   pressing, a control index, chaos, tempo, momentum, player speed and distance.
3. **Explain.** Key moments say why they matter. Storylines open and develop as patterns build (a side on top,
   a flank being targeted and the defender facing it, a defender losing duels late, a booked player still
   fouling, a side chasing the game), with milestones and a "story so far" every 15 minutes. For the decisive
   goal, a multi-agent investigation finds the real cause and says what it wasn't.
4. **Render.** Broadcast overlays (score bug, lower thirds, speed and distance name tags) exported as a timed
   JSON track and WebVTT; and a Studio Pack: 30- and 60-second presenter scripts with graphics cues, a highlights
   rundown with timecodes (CMX3600 EDL and CSV for editing suites), social posts, push alerts and stat cards.
5. **Personalise.** Five languages (including Arabic, right to left), favourite club, follow one player all
   match, fan or analyst depth, one-number focus, spoiler-free mode, and club- or player-framed studio packs.

**The agents.** Both the match pipeline and the goal investigation are **Microsoft Agent Framework**
workflows. In the investigation, an investigator (Claude Haiku 5.5 with read-only match tools) proposes causes
onto a shared evidence board; a sceptic tries to break every claim; a code verifier keeps only claims backed by
the events they cite; a producer writes only what survived, and its text is fact-checked. If a Claude role
fails mid-run, its statistical counterpart takes over and the result records the hand-over. The match analyst
is exposed over **A2A** (Agent Framework's A2A integration) and over **MCP** for **GitHub Copilot agent mode**.

**Why it is different: it can prove it.** Each synthetic match has a hidden cause whose effect we measure by
re-playing the match 120 times with and without it. On 59 unseen matches the agents name the real cause first
75% of the time; the same model reading the raw log, without tools and checks, manages 20% and makes up 69% of
its claims. We publish the misses too.

**Built to deploy.** Server-side keys, bring-your-own-key, saved results, spend caps and rate limits; per-feed
write tokens and limits; fictional names everywhere by default, with a compliance test; 107 automated tests; CI
publishing a container image; a smoke test that checks a deployment without calling a model.

**Microsoft and GitHub technologies used:** Microsoft Agent Framework (workflows, executors, fan-out/fan-in,
switch-case routing, A2A), GitHub Copilot agent mode via MCP, GitHub Actions and GitHub Container Registry,
[Azure Container Apps, once deployed]. Also: Claude Haiku 5.5, FastAPI, React + TypeScript, Docker.

## Links
- Demo video (under 2 minutes): [YouTube or Vimeo URL]
- Live app (no login): [Azure Container Apps URL]
- Code: [public GitHub URL]

## Testing instructions
- No login. Start on the landing page: **Find out what decided the 72nd-minute goal** (the investigation),
  **Watch Northbridge v Calder Vale live** (match centre with storylines), **Live Studio** (press *Kick off a
  new synthetic match*), and **Studio Pack** from any match centre.
- Saved AI results load instantly. "Run fresh" calls the model on a rate-limited demo key; judges can add
  their own Anthropic key in the Model menu.
- A2A agent card: `[app URL]/a2a/.well-known/agent-card.json`. Ingestion contract: `[app URL]/api/schema`.

## Data disclosure
All matches are synthetic. Team strengths are calibrated from public statistics for a real season, but every
club, player, stadium and official shown is fictional, and every event is generated by the simulation. No
crests, badges, photos, footage or real match data are used.
