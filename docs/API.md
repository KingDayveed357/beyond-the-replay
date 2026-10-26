# Beyond the Replay API: ingest a match in five minutes

You send us synthetic match events as they happen; we send back match intelligence (stats, key moments,
storylines, overlay cues, studio packs) to every viewer, live. Nothing in this path calls an AI model, so it is
free to test as much as you like.

- **Interactive reference:** `<your host>/docs` (try every call from the browser)
- **Machine-readable contract:** `<your host>/api/schema` (JSON Schema) and `<your host>/openapi.json`
- **A complete example match:** [`samples/match-feed.json`](../samples/match-feed.json) (950 events, 5 goals), or `<your host>/api/feeds/sample` for a fresh one
- **Watch any feed:** `<your host>/studio/<feed_id>`

## The three calls

```
1. POST /api/feeds                     match sheet   ->  feed_id + write_token
2. POST /api/feeds/{feed_id}/events    a batch       ->  accepted / rejected (with reasons)   (repeat ~every second)
3. GET  /api/feeds/{feed_id}/live      (viewers)     ->  a stream of what's new
```

### 1. Open a feed with a match sheet

Who is playing. Ids are yours to choose; events refer to them.

```json
{
  "home": {"code": "SBR", "name": "Seabright Albion", "colours": ["#0057B8", "#FFFFFF"]},
  "away": {"code": "HLD", "name": "Halden Town", "colours": ["#241F20", "#FFFFFF"]},
  "roster": {
    "SBR-RW":  {"team": "SBR", "role": "RW",  "name": "Kofi Ashby"},
    "SBR-CMR": {"team": "SBR", "role": "CMR", "name": "Leon Marby"},
    "HLD-LB":  {"team": "HLD", "role": "LB",  "name": "Nils Grieve"}
  },
  "metadata": {"venue": "The Pavilion", "kickoff": "Sat 15:00"}
}
```

Response (`201`):

```json
{"feed_id": "fa691ac6736", "write_token": "…keep this…", "events_url": "/api/feeds/fa691ac6736/events",
 "live_url": "/api/feeds/fa691ac6736/live", "limits": {"max_batch": 500, "max_events": 4000}}
```

The write token is shown **once**. Anyone can watch a feed; only the token holder can write to it.

### 2. Push events

Header `Authorization: Bearer <write_token>`. Body:

```json
{"events": [
  {"id": "e00000", "t": 7.5, "team": "SBR", "player_id": "SBR-RW", "type": "pass", "outcome": "success",
   "x": 52.5, "y": 6.9, "end_x": 65.6, "end_y": 17.3, "opponent_id": null, "receiver_id": "SBR-CMR",
   "possession_id": "p0000", "under_pressure": false, "speed_kmh": 54.0}
], "final": false}
```

Response:

```json
{"feed_id": "fa691ac6736", "accepted": 1, "rejected": [], "rejected_count": 0, "events_total": 1,
 "stage_ms": {"ingest": 0.7, "interpret": 6.1, "explain": 0.0, "render": 0.0, "narrate": 0.6, "publish": 0.0},
 "pipeline": ["ingest", "interpret", "explain", "render", "narrate", "publish"]}
```

Send `"final": true` with the last batch (full-time). The feed then closes and viewers get a full-time message.

### 3. Watch it

Open `/studio/<feed_id>` in a browser, or read the stream: `GET /api/feeds/{feed_id}/live?lang=en`
(server-sent events). The first message is a `snapshot` of everything so far; after that you only get what
each batch adds: `event`, `state` (once a minute), `moment`, `cue`, `storyline`, `milestone`, `summary`,
`ingest` (the batch receipt) and finally `phase` (full-time). `lang` is `en`, `es`, `fr`, `pt` or `ar`.

## What an event means

| Field | Meaning |
|---|---|
| `id` | Your id for the event, unique in the feed (1-32 characters) |
| `t` | **Seconds since kick-off** (0-6000). Events must arrive in clock order; equal times are fine |
| `team`, `player_id` | Who acted. The player must be on the roster and play for that team |
| `type` | `pass`, `carry`, `dribble`, `cross`, `shot`, `foul`, `card`, `tackle`, `interception`, `clearance` |
| `outcome` | `success` or `fail` for actions; `goal`, `saved` or `off_target` for shots |
| `x`, `y` | Where it started, in metres (see the pitch below) |
| `end_x`, `end_y` | Where the ball (or the player carrying it) ended up, or `null` |
| `opponent_id` | The opponent involved: the defender beaten in a dribble, the player tackled, or `null` |
| `receiver_id` | Who a pass or cross was meant for, or `null` |
| `possession_id` | Groups the events of one spell of possession, or `null` |
| `under_pressure` | `true` if an opponent was closing the player down |
| `speed_kmh` | Ball speed for passes and shots, running speed for carries and dribbles, or `null` |

Every field is required: use `null` where it does not apply. Extra fields are rejected, so typos surface.

### The pitch

```
 y = 68 ┌───────────────────────────────────────────┐
        │                     │                     │
        │  home goal          │          away goal  │   home attacks →  (towards x = 105)
        │  (x = 0)            │          (x = 105)  │   away attacks ←  (towards x = 0)
        │                     │                     │
 y = 0  └───────────────────────────────────────────┘
       x = 0                x = 52.5               x = 105        (metres)
```

## What makes a good feed

- **Roles matter.** Give full-backs the roles `RB` and `LB`: the "is he tiring?" and "keep coming down the
  left" storylines use them. Other roles: `GK`, `CB1`, `CB2`, `DM`, `CMR`, `CML`, `RW`, `ST`, `LW`.
- **Goals are shots** with `outcome: "goal"`. Bookings are `type: "card"`.
- **Batch about once a second** while live (a few to a few hundred events). Replaying a finished match? Batches
  of up to 500 work, and the whole match is processed in seconds.
- **Duels feed the storylines.** A dribble with `opponent_id` set records a one-on-one: `success` means the
  defender was beaten.

## Errors

| Status | When | What to do |
|---|---|---|
| `200` with `rejected` entries | Some events were invalid | Fix those events; the rest were accepted. Each rejection has `index`, `id` and a plain `reason` |
| `400` | The sheet or batch makes no sense (e.g. two teams with the same code) | Read `detail.message` |
| `401` | Missing or wrong write token | Send `Authorization: Bearer <write_token>` |
| `404` | Unknown feed, or it expired (feeds live 3 hours) | Open a new feed |
| `409` | The feed has ended (you already sent `final: true`) | Open a new feed |
| `422` | The JSON has the wrong shape (a missing team code, `events` not a list) | `detail` names each field |
| `429` | Too many live feeds or demo matches right now | Wait a few minutes |

Typical rejection reasons: `duplicate id`, `out of order: t=… is before the last accepted event`,
`unknown player 'X'`, `SBR-RW does not play for HLD`, `x/y must be on the pitch (0-105 by 0-68 metres)`,
`unexpected fields secret`.

## Limits

500 events per batch, 4,000 per feed, 24 live feeds per server, feeds expire after 3 hours.

## Copy-paste examples

**PowerShell (Windows)**

```powershell
$H = "http://localhost:8000"
$json = "application/json; charset=utf-8"
$sample = Get-Content samples\match-feed.json -Raw -Encoding UTF8 | ConvertFrom-Json
$sheet = [Text.Encoding]::UTF8.GetBytes(($sample.sheet | ConvertTo-Json -Depth 10))
$feed = Invoke-RestMethod -Method Post "$H/api/feeds" -ContentType $json -Body $sheet
$auth = @{ Authorization = "Bearer $($feed.write_token)" }
$batch = [Text.Encoding]::UTF8.GetBytes((@{ events = @($sample.events[0..99]); final = $false } | ConvertTo-Json -Depth 10))
Invoke-RestMethod -Method Post "$H$($feed.events_url)" -Headers $auth -ContentType $json -Body $batch
Start-Process "$H/studio/$($feed.feed_id)"
```

Windows PowerShell 5.1 sends text in the old Windows encoding unless you convert it to UTF-8 bytes as above, so
accented names (Valdés, Sørensen) would otherwise arrive garbled and the request would be rejected.

**curl (macOS, Linux, Git Bash)**

```bash
H=http://localhost:8000
FEED=$(curl -s -X POST $H/api/feeds -H "Content-Type: application/json" -d @sheet.json)
TOKEN=$(echo "$FEED" | python -c "import json,sys; print(json.load(sys.stdin)['write_token'])")
ID=$(echo "$FEED" | python -c "import json,sys; print(json.load(sys.stdin)['feed_id'])")
curl -s -X POST $H/api/feeds/$ID/events -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @batch.json
```

**Python: stream a whole new match like a live provider**

```bash
python scripts/feed_simulator.py http://localhost:8000 --speed 30
```

## Getting things out

| Call | Gives you |
|---|---|
| `GET /api/feeds/{id}?lang=es` | Everything so far: timeline (states, moments, cues, players) and narrative |
| `GET /api/feeds/{id}/studio-pack?format=md` | Presenter scripts, highlights, social posts and alerts as of now (`json`, `md`, `edl`, `csv`) |
| `GET /api/feeds` | All live feeds |
