# Demo film: "Was it really the booking?"

Production blueprint for the Inside the Game submission video. Everything below was checked against the live
deployment on 26 Oct 2026 (`/api/...` responses, saved investigations, answer key, benchmark). If the app changes,
re-check the facts in the table at the end before recording.

**Hard rules from the official rules:** under 2:00 (judges may stop at 2:00); show the project running; public
YouTube/Vimeo link; **no third-party trademarks, copyrighted music or footage** without permission. Our consequences:
no broadcast footage, no club crests or league logos, no commercial music. The app shows fictional clubs and players
by default, and its match sounds are synthesised in the browser (no recordings), so the product itself is safe to film.

---

## A. Creative recommendation

### Three directions considered

| | 1. The Booking (recommended) | 2. Matchday Control Room | 3. Can You Trust an AI Pundit? |
|---|---|---|---|
| **Central idea** | A football mystery: the obvious culprit vs the real cause, solved on screen and proven against an answer key. | A producer's view: events stream in, the product turns them into storylines, graphics, scripts and alerts in real time. | AI explanations are confident and often wrong; ours are checked and scored. |
| **Opening hook** | "71': a booking. 72': a goal." The viewer makes the connection everyone makes. | A blank pipeline lighting up as a brand-new match streams in. | "Same AI model. 20% without checks. 75% with them." |
| **Tone** | Suspense, then a satisfying reveal. Human, a little playful (you play along). | Calm competence, broadcast-gallery energy. | Sober, analytical, research-paper confident. |
| **Demonstration** | Make your call → agents investigate → "what it wasn't" → reveal the true cause → live pipeline montage → proof. | Live Studio → storylines → match centre → Studio Pack → overlays. | Benchmark page → investigation → verifier rejections → answer key. |
| **Why judges might love it** | Instant comprehension, a payoff, and the multi-agent design is the plot, not a slide. Hits every rubric line. | Directly mirrors the challenge's five stages; strong "Enterprise" signal. | Strong for technical judges; honesty is rare. |
| **Risk** | Must still show the live pipeline (brief requirement) without breaking the story. | No single memorable moment; looks like other dashboard entries. | Opens on numbers, not football; weak emotional hook; abstract. |

**Decision: Direction 1, "The Booking", with Direction 2 compressed into a 24-second "it works live" montage and
Direction 3's numbers as the closing proof.** The mystery gives judges a reason to keep watching, the investigation
*is* the agentic design (Agentic Design & Innovation, 20%), the reveal proves it (Real-World Impact), the montage covers
the brief's five stages (Category adherence), and the numbers make it credible (Technological Implementation).

### Title
**Beyond the Replay: Was it really the booking?**

### One-sentence pitch
Beyond the Replay turns live match events into football stories you can check: AI agents investigate what really
decided a goal, code verifies every claim, and the answer is scored against a known truth.

### What judges should remember 30 minutes later
"The one where the booking wasn't the cause. You make your call, the agents investigate, and then it proves who was
right. Three in four, against one in five for the same AI without checks."

### The insight behind it
In football (and in AI) the most recent dramatic event gets the blame. Beyond the Replay is built to resist the obvious
story, and because its matches are synthetic, it can *measure* whether it did.

---

## B. Timed storyboard (1:53)

Voice-over (VO) is ~225 words: about 2 words per second, leaving room to breathe. Times are targets; the edit decides.

### Scene 1: The hook (0:00–0:07)
- **Purpose:** create the question before anything is explained.
- **Visual:** black for 0.5 s. Cut to a tight crop of the landing page's question strip (the timeline in the right-hand card): the yellow card at **71'** and the goal at **72'** with "57 seconds apart · Coincidence, or cause?". Slow push-in (105% → 115%).
- **Product action:** none (recorded from `/`, hero card).
- **VO (from 0:02):** "Seventy-one minutes: a booking. Seventy-two: a goal."
- **On-screen text:** none beyond the UI.
- **Editing:** hard cut from black; no logo.
- **Audio:** the app's referee whistle (two blasts) on the word "booking"; the app's crowd roar swelling under "goal", ducked under VO. No music yet.
- **Assets:** `REC-01` (landing hero, 4K-sharp crop), `SFX-card`, `SFX-goal` (recorded from the app).

### Scene 2: The problem (0:07–0:17)
- **Purpose:** name the trap everyone falls into.
- **Visual:** pull back to the full landing headline: "A booking at 71'. A goal at 72'. *Was the booking really the cause?*" Hold.
- **VO:** "Everyone connects the two: commentators, stats feeds, and now AI. It's the obvious story. In our simulated matches, it's right about two times in a hundred."
- **On-screen text (lower left, 0:13–0:17):** "The obvious story: right about 2% of the time*" and, small: "*simulated test matches, measured against a known cause".
- **Editing:** one cut, no movement during the stat. Let the number land.
- **Audio:** low, sparse music bed enters at 0:10 (see section E), −28 LUFS.
- **Assets:** `REC-01`.

### Scene 3: The reveal (0:17–0:27)
- **Purpose:** introduce the product as the answer to the problem.
- **Visual:** wordmark card on the app's ink background: "Beyond *the* Replay" (Instrument Serif, the app's typeface), then a subline fades in: "Football stories you can check." Then cut to the landing page scrolling to "One pipeline, five stages".
- **VO:** "Beyond the Replay follows a match event by event. When a goal matters, it investigates why, and then checks its own work."
- **On-screen text:** "Beyond *the* Replay" / "Football stories you can check."
- **Editing:** 2.5 s card, gentle fade (8 frames). Then a straight scroll (no zoom).
- **Audio:** music continues; no SFX.
- **Assets:** `GFX-01` (title card), `REC-02` (landing scroll).

### Scene 4: Your call (0:27–0:35)
- **Purpose:** put the viewer in the game.
- **Visual:** the investigation page `/match/m300080` showing "Your call first: What decided Highcross's goal at 72'?" with the goal move on the pitch. Cursor glides to **"A defender tiring"** and clicks.
- **Product action:** one deliberate click.
- **VO:** "But first, you make the call."
- **On-screen text:** none (the UI is the text).
- **Editing:** zoom to 125% on the four options as the cursor approaches; snap back on click.
- **Audio:** the app's tap sound on click. Music dips 3 dB.
- **Assets:** `REC-03`.

### Scene 5: The investigation (0:35–0:55)
- **Purpose:** show the multi-agent design as the plot, and that facts are checked.
- **Visual (in order):**
  1. The four stage cards light up: *Looks for causes · Pushes back · Checks the facts · Writes it up* (0:35–0:41).
  2. The headline: **"Caleb Ingram's fading legs, not Elstree's booking, opened the door for Ashhurst"** with the cited events glowing green on the pitch (0:41–0:48).
  3. Crop to **"What it wasn't: the booking of Joel Elstree at 71'"** (0:48–0:55).
- **Product action:** none after the click (the result appears; scroll slowly to "What it wasn't").
- **VO:** "Then four agents take the case. A detective proposes causes. A devil's advocate tries to break them. A fact-checker, plain code with no AI, throws out anything the match events don't support. Only what survives reaches the screen."
- **On-screen text (small, top left, 0:36–0:46):** "Saved AI investigation (Claude Haiku 5.5) · one Microsoft Agent Framework workflow · re-run live with your own key".
- **Editing:** two punch-ins (stage row, then headline). Keep each readable for ≥ 2.5 s.
- **Audio:** music builds slightly. No SFX.
- **Assets:** `REC-03` continued.
- **Honesty note:** this result was computed earlier and saved; the caption says so. Do not narrate it as happening now.

### Scene 6: The payoff (0:55–1:08)
- **Purpose:** the proof moment: the answer key.
- **Visual:** cursor clicks **Reveal the answer**. "**It got it right.** And so did you. You called it." Then the effects table: "Defender tired: Caleb Ingram **+0.27** goals" with the bar, and "The booking **0.00**".
- **Product action:** one click.
- **VO:** "Because these matches are synthetic, we know the truth. We replayed this one a hundred and twenty times, with and without the tiring defender. The AI got it right. So did you."
- **On-screen text:** none (the UI says it). Optional underline on "+0.27" and "0.00".
- **Editing:** hold 1 s of silence after "It got it right" appears, before VO resumes.
- **Audio:** the app's rising "right" fanfare and short applause on the reveal. Music drops out for 1 s, then returns.
- **Assets:** `REC-03` continued.

### Scene 7: It works live (1:08–1:33), a four-shot montage, about 6 s each
- **Purpose:** cover the brief's pipeline (ingest, interpret, explain, render, personalise) at speed.
- **Shots:**
  1. **Live Studio** `/studio`: click *Kick off a new synthetic match*; the six pipeline boxes fill with millisecond timings; the event log scrolls (1:08–1:14).
  2. **A storyline arrives** in "What's building" (e.g. "keep coming down the left" or "Is … tiring?") with a milestone below (1:14–1:20).
  3. **Match centre** `/live/m300121`: language switches to **العربية** and the layout flips right-to-left; then *Follow a player* (1:20–1:27).
  4. **Studio Pack** `/pack/m300080`: the 60-second presenter script, then the highlights rundown with timecodes and the *Edit list (.edl)* button (1:27–1:33).
- **VO:** "And it works live. Any data provider can push events in as they happen. It notices what's building, minute by minute. Every fan gets their own match, in five languages. And studios get presenter scripts, highlight edit lists and alerts from the same checked data."
- **On-screen text (one per shot, lower left):** "Ingest → Interpret → Explain → Render → Narrate" · "Storylines, live" · "5 languages · your club · your player" · "Scripts · edit lists · alerts".
- **Editing:** straight cuts on VO sentence boundaries; tempo up. Small 110% push-ins only.
- **Audio:** the app's storyline chime on shot 2 and the milestone tick; music at its fullest here (−24 LUFS under VO).
- **Assets:** `REC-04`, `REC-05`, `REC-06`.

### Scene 8: The proof (1:33–1:46)
- **Purpose:** credibility, including honesty.
- **Visual:** the **How accurate is it?** page, main table; highlight the **AI agents 75%** row and the **Claude reading the raw log 20%** row (1:33–1:42). Hard cut to the other match's reveal: "**It got this one wrong.**" (1:42–1:46).
- **VO:** "On fifty-nine matches it had never seen, the agents found the real cause three times in four. The same model without tools or checks: one in five. And when it's wrong, it says so."
- **On-screen text:** "75% vs 20%" large, briefly, over the table. Small: "59 unseen simulated matches".
- **Editing:** highlight boxes drawn in the edit (thin lines, app's mint `#8fe3b0` for 75%, coral `#ff6f61` for 20%).
- **Audio:** music thins out. The app's soft "wrong" two-note on the miss.
- **Assets:** `REC-07` (benchmark), `REC-08` (miss reveal on `/match/m300121`).

### Scene 9: The close (1:46–1:53)
- **Purpose:** an earned, memorable ending.
- **Visual:** the landing hero (the 71'/72' card again, completing the loop), then the wordmark card.
- **VO:** "Beyond the Replay. Football stories you can check."
- **On-screen text:** "Beyond *the* Replay" · "Football stories you can check." · small line: "Built with Microsoft Agent Framework · Azure Container Apps · A2A · MCP" · the live URL.
- **Editing:** 1 s fade to black after the last line. Total 1:53.
- **Audio:** music resolves; a final soft crowd swell from the app's goal sound at −30 LUFS; silence for the last 0.5 s.
- **Assets:** `REC-01`, `GFX-02` (end card).

**Optional line (only if you have spare seconds):** in the match the AI gets wrong, the live storyline "Is Kwame
Kelhurst tiring?" fired at 81', five minutes before the 86' goal, and the answer key blames exactly that defender.
It's true and impressive, but it needs 10 seconds to explain, so it's cut from the primary film.

---

## C. Recording plan (Windows)

### One-time setup (15 minutes)
1. **Warm the app:** in Azure set **min replicas = 1** at least 10 minutes before recording; open `/` once.
2. **Display:** Windows Settings → Display → Scale **100%**, highest resolution. If your screen is 1920×1080 or larger, record at **1920×1080**. If it is smaller (e.g. 1366×768), set Chrome zoom to **80%** and record the window; the edit will upscale less than you'd think, but text must still be sharp. Check by recording 5 seconds and zooming in.
3. **Browser:** a fresh **Incognito** window for every take: storage is empty, so "Your call first" appears and sound is on by default. Hide extensions. Use **F11** (full screen) so no tabs or address bar show. Chrome zoom **110%** for legibility at 1920×1080.
4. **Windows:** Focus Assist / Do not disturb **on**; close chat apps; hide the taskbar (it's hidden in F11 anyway).
5. **OBS Studio (free):** Settings → Video: base and output 1920×1080, **60 fps** (smoother cursor; export at 30). Output: recording format **MKV** (remux to MP4 after; survives crashes), encoder hardware (NVENC/QuickSync) or x264 "veryfast", CRF 18 / CQP 18. Audio: **Desktop Audio** on track 1 (app sounds), **mic off** (record VO separately). Add a **Display Capture** or **Window Capture** (Chrome) source.
6. **Cursor:** Windows mouse pointer size 2, normal speed. Move slowly and in straight lines; pause 0.5 s before each click.

### Takes (record each 2–3 times; keep the best)

| ID | URL / start state | Exact actions | Keep |
|---|---|---|---|
| REC-01 | `/` (incognito) | Wait 2 s for the hero to settle. Do not move the mouse for 8 s. Then move the mouse away. | Hero headline and the 71'/72' card, still. |
| REC-02 | `/` | Scroll slowly (mouse wheel, 1 notch per second) to "One pipeline, five stages". | 6 s smooth scroll. |
| REC-03 | `/match/m300080` (new incognito) | Wait 3 s. Click **A defender tiring**. Wait for the stages and result (about 3 s). Scroll slowly to "What it wasn't". Scroll to **Reveal the answer**, pause 1 s, click. Hold 6 s on the result and the effects table. | The whole call → investigation → reveal sequence, uncut. |
| REC-04 | `/studio` | Select **60×**. Click **Kick off a new synthetic match**. Keep recording for 90 s without touching anything. | Pipeline timings filling; event log; the first storyline and milestones arriving. |
| REC-05 | `/live/m300121` (new incognito) | Select **60×**, click **Kick off**, wait ~15 s (goals, moments, sounds). Open the Language menu → **العربية**. Wait 4 s. Back to English. Choose *Follow a player* → a scorer. | RTL flip; follow-player card. |
| REC-06 | `/pack/m300080` | Toggle **60s** script. Scroll to the highlights rundown. Hover **Edit list (.edl)**. | Script; timecodes; downloads. |
| REC-07 | `/benchmark` | Scroll to the main results table. Hold 6 s. | The 75% / 78% / 20% table, readable. |
| REC-08 | `/match/m300121` (new incognito) | Click any call, wait for the result, click **Reveal the answer**. Hold 4 s. | "It got this one wrong." |
| SFX | (from REC-03/04/05 desktop audio) | — | Whistle, goal roar, tap, chime, right/wrong cues, cleanly isolated. |

**Never press "Run fresh"** on camera (no key is configured; it would show an error, and it's not part of the story).
Do not open the Model menu or any settings that show keys.

### Graphics to make
- `GFX-01` title card and `GFX-02` end card: ink background `#0b0d0c`, chalk text `#eef0ea`, "the" in italic, Instrument Serif (free on Google Fonts; install it so the editor can use it). Subline in Inter.
- Lower-left captions throughout: Inter 600, white at 90%, 34 px on a 1080p canvas, no boxes or glows.
- Highlight boxes for Scene 8: 2 px rounded rectangles, mint `#8fe3b0` and coral `#ff6f61`.

---

### Automated takes and rough cut (already done)

The eight takes, cards and a silent 1:53 rough cut were generated by script against the live site:

```bash
pip install playwright imageio-ffmpeg && python -m playwright install chromium
python scripts/video/record_takes.py https://<app>        # video/takes/REC-0x.mp4 + markers.json
python scripts/video/render_cards.py https://<app>        # video/cards/*.png (title, end, captions)
python scripts/video/assemble_cut.py                       # video/rough_cut.mp4 + video/segments/
```

Re-record any single take with `--only REC-03`; the assembler re-times its cuts from the markers. The scripted
takes have no audio: the app's sounds play in the browser, so capture them separately (see section E).

## D. Editing workflow

**Essential (all free):**
- **OBS Studio**: screen recording.
- **Clipchamp** (built into Windows 11, Microsoft): editing, zoom/pan, text, auto-captions, 1080p export. Free tier exports 1080p without a watermark.
- **Audacity**: record and clean the voice-over (noise reduction, normalise).

**Optional:** **DaVinci Resolve** (free) if you want frame-accurate keyframed zooms and proper loudness metering. Skip it if time is short; Clipchamp is enough for this cut.

**Order of work:**
1. Record VO first (section E), so the picture is cut to the voice.
2. Lay the VO on the timeline with gaps as timed above.
3. Drop in the takes, trim to the VO, then add zooms (Clipchamp: *Crop / Pan & zoom*).
4. Add the title and end cards and the lower-left captions.
5. Add music, then the app's own sounds from the desktop-audio track.
6. Auto-captions, then correct them against `docs/video/captions.srt`.
7. Export, watch it twice (once muted), fix, re-export.

Code-generated motion graphics are not needed: the product UI already provides the visuals, and simpler is safer.

---

## E. Audio and captions

### Narration (final, about 225 words)
> Seventy-one minutes: a booking. Seventy-two: a goal.
>
> Everyone connects the two: commentators, stats feeds, and now AI. It's the obvious story. In our simulated matches, it's right about two times in a hundred.
>
> Beyond the Replay follows a match event by event. When a goal matters, it investigates why, and then checks its own work.
>
> But first, you make the call.
>
> Then four agents take the case. A detective proposes causes. A devil's advocate tries to break them. A fact-checker, plain code with no AI, throws out anything the match events don't support. Only what survives reaches the screen.
>
> Because these matches are synthetic, we know the truth. We replayed this one a hundred and twenty times, with and without the tiring defender. The AI got it right. So did you.
>
> And it works live. Any data provider can push events in as they happen. It notices what's building, minute by minute. Every fan gets their own match, in five languages. And studios get presenter scripts, highlight edit lists and alerts from the same checked data.
>
> On fifty-nine matches it had never seen, the agents found the real cause three times in four. The same model without tools or checks: one in five. And when it's wrong, it says so.
>
> Beyond the Replay. Football stories you can check.

**Delivery:** conversational, slightly lower than your normal pitch, unhurried. Smile on "So did you." Pause a full beat
after "two times in a hundred" and after "So did you." Record in a small furnished room (soft surfaces), phone or
headset mic 15 cm from the mouth, slightly off-axis. Three full takes; pick the best line from each.
In Audacity: Noise Reduction (profile from 2 s of silence), Compressor gentle, Normalise to −1 dB peak.

### Music
Sparse, minimal electronic or ambient with a slow pulse (think "tense but optimistic", 90–100 bpm, no vocals).
Source: **YouTube Audio Library** (Studio → Audio Library), filtered to "No attribution required". Download it and keep
the licence note. Or use no music: the app's own sounds plus voice carry this film well.

### Sound design (all from the app, recorded via OBS desktop audio)
Whistle (Scene 1), goal roar (Scenes 1 and 9), tap (Scene 4), storyline chime and milestone tick (Scene 7),
"right" fanfare (Scene 6), "wrong" notes (Scene 8).

### Levels
Voice around −16 LUFS (peaks ≤ −3 dBFS); music −28 to −24 LUFS under voice; SFX peaks around −10 dBFS; final mix
about −14 LUFS integrated (YouTube's target).

### Captions
Burned-in captions plus an uploaded `.srt` on YouTube. Style: Inter 600, white with a 60% black shadow, bottom
centre, max two lines, never covering the UI being discussed. Use `docs/video/captions.srt` (timed to this
storyboard) and nudge timings after the edit. The film must make sense on mute: the on-screen lines in Scenes 2, 5, 7
and 8 carry the argument without sound.

---

## F. Quality-control checklist

**Story**
- [ ] The question ("Was it really the booking?") is clear by 0:10.
- [ ] A first-time viewer can say what the product does by 0:30.
- [ ] The reveal (Scene 6) has a pause and lands.
- [ ] The live pipeline (Scene 7) shows all five stages of the brief.

**Accuracy (re-check against the live app)**
- [ ] Booking at 71' (Joel Elstree), goal at 72' (Yann Ashhurst), Saltcliffe 3–1 Highcross.
- [ ] AI headline: "Caleb Ingram's fading legs, not Elstree's booking, opened the door for Ashhurst".
- [ ] Answer key: Defender tired, Caleb Ingram, +0.27; booking 0.00; 120 paired replays.
- [ ] 59 unseen matches; agents 75% (rounded "three in four"); same model without tools 20% ("one in five").
- [ ] "About 2%": the obvious-story baseline on simulated test matches (shown on the accuracy page).
- [ ] The saved investigation is labelled "saved", never described as running live.
- [ ] Nothing in the video claims the agents beat the statistics engine (78%): they don't.

**Legal and safety**
- [ ] No real club, player, league or broadcaster names, logos, crests or footage.
- [ ] Music has a licence that allows use without attribution, or no music.
- [ ] No keys, emails, Azure portal, terminal or settings visible.

**Visual and audio**
- [ ] All UI text readable at 1080p on a laptop screen (check at 100% and on a phone).
- [ ] No stray cursor movements, loading spinners, or the browser chrome.
- [ ] The Feedback pill (bottom right) doesn't distract: crop or frame around it where it competes.
- [ ] Voice clear over music everywhere; no clipping; no silence gaps over 1.5 s except the deliberate pause.
- [ ] Captions match the VO word for word.

**Submission**
- [ ] Length **1:55 or less** (hard limit 2:00).
- [ ] Uploaded to YouTube as **Public** or **Unlisted**, link works in a private window.
- [ ] Link pasted into `docs/SUBMISSION.md` and the submission email.

---

## G. Export settings

YouTube/Vimeo, web viewing, 2-minute limit:
- **1920×1080, 16:9, 30 fps** (record at 60, export 30: smaller file, UI motion still smooth).
- **H.264 (High profile), MP4**, bitrate 12–16 Mbps (Clipchamp: 1080p export).
- **AAC 48 kHz, 320 kbps**, stereo.
- Upload with title "Beyond the Replay: Was it really the booking? (Inside the Game hackathon)" and the `.srt` file.

---

## Facts used (verified 26 Oct 2026 against the live deployment)

| Fact | Source |
|---|---|
| Saltcliffe 3–1 Highcross, Cliffside Ground; booking Joel Elstree 71'; goal Yann Ashhurst 72' | `/api/matches/m300080` |
| AI headline and "ruled out: the booking" (Claude Haiku 5.5, saved) | `/api/matches/m300080/incidents/e00759/saved-investigation` |
| True cause FATIGUE, Caleb Ingram (+0.27); 120 paired replays | `/api/matches/m300080/incidents/e00759/truth` |
| Northbridge 4–1 Calder Vale: AI blamed Lindqvist (static); truth Kelhurst tiring; "It got this one wrong" | `/api/matches/m300121/...` |
| Agents 74.6% / statistics 78.0% / same model on raw log 20.3%, n = 59 | `/api/benchmark` → `agents_heldout_v21` |
| Obvious story (booking) right 1.8% | `results/phase0.json` → `test_scores.salience` |
