# Demo video: under 2 minutes

Rules: under 2:00 (judges may stop at 2:00), shows the project running, public link on YouTube or Vimeo,
**no third-party trademarks, crests, broadcast footage or copyrighted music**. The app shows fictional clubs
and players by default, so the whole recording is trademark-free. Record the real app; no mock-ups.
**Recording costs nothing:** every screen uses saved AI results, ingestion and templates. Do not press
"Run fresh" on camera.

The story, in the app's fictional names:
- **Saltcliffe 3–1 Highcross** (`/match/m300080`, Cliffside Ground): Joel Elstree is booked at 71', Yann
  Ashhurst scores at 72'. The AI says it was Caleb Ingram tiring, not the booking, and it is right.
- **Northbridge 4–1 Calder Vale** (`/live/m300121`): the live match centre, storylines and Studio Pack.
- **Live Studio** (`/studio`): a brand-new synthetic match streamed in through the ingestion API.

## Before recording

- [ ] Fresh browser profile, window 1440×900, zoom 100%, notifications off.
- [ ] App running (deployed URL preferred). Open each page once so saved results are warm.
- [ ] Preferences reset: English, Fan view, no club, no player, spoiler-free off. Clear site data so "Your call first" shows.
- [ ] Royalty-free music only (or none). Voice-over recorded separately. Captions on.
- [ ] Match sounds on (speaker icon in the top bar) and captured by the screen recorder. They are synthesised in
      the browser (`web/src/sound.ts`): whistles, crowd and chimes made from tones and noise, with no recordings, so
      they are safe for the video. Keep them under the voice-over: record at about half volume.

## Script (about 1:55)

| Time | Screen | Voice-over |
|---|---|---|
| 0:00–0:07 | Landing: "A booking at 71'. A goal at 72'. Was the booking really the cause?" | "Football stories don't end with the scoreline. Beyond the Replay turns synthetic match events into intelligence you can trust." |
| 0:07–0:22 | **Live Studio** → *Kick off a new synthetic match* (60×). Pipeline stages light up with timings; events stream in | "A data provider pushes events as they happen. Every batch runs through a Microsoft Agent Framework pipeline: ingest, interpret, explain, then render and narrate in parallel, and only what's new is published." |
| 0:22–0:34 | Same page a few seconds later: a storyline appears, "the story so far", a milestone | "It doesn't just log events, it notices what's building: a side on top, a flank being targeted, a defender starting to tire." |
| 0:34–0:50 | **Northbridge v Calder Vale live**: score bug, lower third, then My club, follow a player, language → Español, then Arabic | "Every fan gets their own match: their club, one player to follow, fan or analyst depth, five languages, even right to left." |
| 0:50–1:04 | **Studio pack**: presenter script (60s), highlights rundown with timecodes, push alerts, download the EDL | "For studios and streaming: presenter scripts, a highlights edit list that drops straight into an editing suite, social posts and alerts, generated in under a second from the same checked data." |
| 1:04–1:28 | Landing → **Find out what decided the 72nd-minute goal**. "Your call first": pick *A defender tiring*. Four stages light up; "What really decided it"; "What it wasn't" | "Elstree was booked at 71'. Ashhurst scored a minute later. Was it the booking? Make your call, then AI agents investigate: an investigator proposes causes, a sceptic tries to break them, code checks every claim. The answer: Caleb Ingram was tiring. Not the booking." |
| 1:28–1:36 | **Reveal the answer**: "It got it right. And so did you." | "The match is synthetic, so we know the real cause: the AI got it right, and so did you." |
| 1:36–1:47 | **How accurate is it?** main table | "On matches it has never seen, the agents find the real cause 75% of the time. The same model without tools and checks: 20%." |
| 1:47–1:55 | Quick cut: `/a2a/.well-known/agent-card.json`, then landing | "And other agents can ask it too, over A2A and MCP. Beyond the Replay." |

## After recording

- [ ] Length under 1:58. Upload to YouTube (public or unlisted) and paste the link in the submission.
- [ ] Re-watch muted: does the story land through the captions alone?
