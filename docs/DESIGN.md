# Design system: "The Inquiry"

A night-match broadcast crossed with an investigation file. It should feel confident and
editorial: serif headlines that read like a match report, monospaced evidence that reads like a
case file, and a pitch that is a working instrument rather than decoration.

## Principles

1. **Every mark is an event.** The pitch shows only the generated event coordinates. No invented
   player movement and no decorative animation. If something moves, it is replaying data.
2. **Colour carries meaning.** Four semantic colours, used for nothing else:
   | token | meaning |
   |---|---|
   | `--supported` mint `#8FE3B0` | verified and survived the sceptic |
   | `--challenged` amber `#F2B84B` | verified but weakened by a sceptic test |
   | `--refuted` coral `#FF6F61` | ruled out, with its reason |
   | `--truth` violet `#A99CFF` | hidden ground truth: evaluation only, outside the investigation |
3. **Teams are told apart by shape, not colour.** Scoring team: solid chalk discs. Conceding team: hollow rings.
4. **Fan first, analyst on demand.** Headline and three beats by default. Numbers, tests and
   scores sit behind an Analyst toggle and a disclosure.
5. **Honesty is a visual element.** "Synthetic match" and the agent mode are always visible.
   Ground truth sits behind an explicit reveal, in its own colour.

## Tokens

| Role | Value |
|---|---|
| Background `--ink` | `#0B0D0C` |
| Surfaces `--ink-2` / `--ink-3` | `#121614` / `#1A201D` |
| Rules `--rule` | `#2A322E` |
| Text `--chalk` / `--chalk-2` / `--chalk-3` | `#EEF0EA` / `#A9B0AA` / `#6E7771` (all ≥ 4.5:1 on `--ink` except `--chalk-3`, used only for non-essential labels at ≥ 14px) |
| Pitch | `#0F1D16`, lines at 16% chalk |

**Typography:** Instrument Serif (headlines, the question), Inter (UI), JetBrains Mono (event IDs,
minutes, numbers). Scale 12 / 14 / 16 / 20 / 28 / 44 / 72px. Fonts are self-hosted (no CDN).

**Spacing:** 4px base, 8 / 12 / 16 / 24 / 32 / 48 / 64. Workspace grid: 12 columns, 24px gutter,
pitch and timeline on 7 columns, investigation on 5. Below 1000px, a single column with the
pitch first.

**Shape:** 2px radius for chips and 6px for panels. Hairline rules instead of shadows. No glass, no gradients on surfaces.

## Motion

- Only for causality and state: the ball travels the goal's build-up path (about 3.5 s), agent
  stages switch on in order, and evidence markers fade in where the data puts them.
- 150 to 250ms ease-out for UI transitions. Agent stages are paced at 450ms for readability, and the real compute
  time is shown beside them, so the pacing is never mistaken for model latency.
- `prefers-reduced-motion`: no ball travel, no staging; everything renders in its final state.

## Components

Top bar → match header → (Pitch + Timeline) | (Agent stages → Verdict → Beats → Ruled out →
All candidates → Ground-truth reveal). The benchmark page reuses the panel, chip and table styles.

**States:** loading (stage strip pulses on the active agent), error (plain sentence plus retry, and
no fake result), empty (no verified explanation: shows "No explanation survived verification"),
complete.

**Accessibility:** all controls are buttons or links with visible focus rings (2px chalk outline).
Evidence chips are keyboard-reachable and announce "event e00123, minute 71". The pitch has a text
alternative listing the build-up. Colour is never the only signal: every status chip carries a word.

## Video and imagery

None in the MVP. We found no verified-licence football footage worth its weight, and generated
video would blur what is synthetic. The data-driven pitch is the hero.
