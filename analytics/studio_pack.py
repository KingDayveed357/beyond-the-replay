"""Studio Pack: everything a studio, broadcaster or streaming platform needs after (or during) a match, generated
automatically from the same checked match data:

  presenter    30- and 60-second autocue scripts with graphics cues
  highlights   a clip rundown with timecodes (JSON, CSV, or a CMX3600 EDL an editing suite can import)
  lower_thirds caption pairs for the graphics engine
  social       a post, a thread and a caption
  push         alerts for goals and full-time
  stat_cards   three graphics-ready comparisons

Deterministic and template-based in five languages: every name, minute and number is copied from the timeline,
so nothing in the pack can disagree with the match data. Personalised packs frame the copy for one club and/or
one player ("for you" alerts, the player's line in the script).
"""
from __future__ import annotations

FPS = 25
WORDS_PER_SECOND = 2.6

P = {
    "en": {
        "open_ft": "Full-time at {venue}: {home} {hs}, {away} {as_}.", "open_live": "{minute} minutes played at {venue}: {home} {hs}, {away} {as_}.",
        "goal": "{scorer} scores for {team} after {minute} minutes{assist}.", "assist": ", set up by {player}",
        "stats": "{team} created {xg} expected goals to {opp_xg}, with {poss}% of the ball.",
        "story": "The story of the match: {title}.", "why": "And the goal everyone will talk about: {headline}.",
        "player": "{player}: {goals} goal(s), {touches} touches, top speed {kmh} km/h.",
        "close": "Every number checked against the match data. Simulated match.",
        "mine_win": "{club} win {score} against {opp}!", "mine_draw": "{club} draw {score} with {opp}.", "mine_loss": "{club} lose {score} to {opp}.",
        "push_goal_title": "GOAL: {home} {score} {away}", "push_goal_body": "{scorer} ({minute}')",
        "push_ft_title": "Full-time: {home} {hs}-{as_} {away}", "push_ft_body": "Expected goals {hxg}-{axg}. {story}",
        "clip_goal": "Goal: {player} ({minute}')", "clip_chance": "Big chance: {player} ({minute}')", "clip_card": "Booking: {player} ({minute}')",
        "lt_goal": "{team} {score}", "cue_score": "SCOREBOARD", "cue_goal": "GOAL CLIP", "cue_stats": "STAT CARD", "cue_story": "STORYLINE", "cue_why": "WHY IT HAPPENED", "cue_player": "PLAYER CARD",
        "card_xg": "Expected goals", "card_shots": "Shots (on target)", "card_poss": "Possession",
        "thread_goals": "Goals: {list}.", "simulated": "Simulated match",
    },
    "es": {
        "open_ft": "Final en {venue}: {home} {hs}, {away} {as_}.", "open_live": "Minuto {minute} en {venue}: {home} {hs}, {away} {as_}.",
        "goal": "{scorer} marca para {team} en el minuto {minute}{assist}.", "assist": ", con pase de {player}",
        "stats": "{team} generaron {xg} goles esperados por {opp_xg}, con un {poss}% de posesión.",
        "story": "La historia del partido: {title}.", "why": "Y el gol del que todos hablarán: {headline}.",
        "player": "{player}: {goals} gol(es), {touches} toques, velocidad máxima {kmh} km/h.",
        "close": "Cada dato, verificado con los datos del partido. Partido simulado.",
        "mine_win": "¡{club} gana {score} a {opp}!", "mine_draw": "{club} empata {score} con {opp}.", "mine_loss": "{club} pierde {score} ante {opp}.",
        "push_goal_title": "GOL: {home} {score} {away}", "push_goal_body": "{scorer} ({minute}')",
        "push_ft_title": "Final: {home} {hs}-{as_} {away}", "push_ft_body": "Goles esperados {hxg}-{axg}. {story}",
        "clip_goal": "Gol: {player} ({minute}')", "clip_chance": "Ocasión: {player} ({minute}')", "clip_card": "Amarilla: {player} ({minute}')",
        "lt_goal": "{team} {score}", "cue_score": "MARCADOR", "cue_goal": "CLIP DEL GOL", "cue_stats": "GRÁFICO", "cue_story": "HISTORIA", "cue_why": "POR QUÉ PASÓ", "cue_player": "JUGADOR",
        "card_xg": "Goles esperados", "card_shots": "Tiros (a puerta)", "card_poss": "Posesión",
        "thread_goals": "Goles: {list}.", "simulated": "Partido simulado",
    },
    "fr": {
        "open_ft": "Fin du match à {venue} : {home} {hs}, {away} {as_}.", "open_live": "{minute}e minute à {venue} : {home} {hs}, {away} {as_}.",
        "goal": "{scorer} marque pour {team} à la {minute}e minute{assist}.", "assist": ", servi par {player}",
        "stats": "{team} ont créé {xg} buts attendus contre {opp_xg}, avec {poss} % de possession.",
        "story": "Le fil du match : {title}.", "why": "Et le but dont tout le monde parlera : {headline}.",
        "player": "{player} : {goals} but(s), {touches} ballons touchés, pointe à {kmh} km/h.",
        "close": "Chaque chiffre est vérifié sur les données du match. Match simulé.",
        "mine_win": "{club} s'impose {score} face à {opp} !", "mine_draw": "{club} fait match nul {score} contre {opp}.", "mine_loss": "{club} s'incline {score} face à {opp}.",
        "push_goal_title": "BUT : {home} {score} {away}", "push_goal_body": "{scorer} ({minute}')",
        "push_ft_title": "Fin du match : {home} {hs}-{as_} {away}", "push_ft_body": "Buts attendus {hxg}-{axg}. {story}",
        "clip_goal": "But : {player} ({minute}')", "clip_chance": "Occasion : {player} ({minute}')", "clip_card": "Carton : {player} ({minute}')",
        "lt_goal": "{team} {score}", "cue_score": "SCORE", "cue_goal": "CLIP DU BUT", "cue_stats": "STATS", "cue_story": "FIL ROUGE", "cue_why": "POURQUOI", "cue_player": "JOUEUR",
        "card_xg": "Buts attendus", "card_shots": "Tirs (cadrés)", "card_poss": "Possession",
        "thread_goals": "Buts : {list}.", "simulated": "Match simulé",
    },
    "pt": {
        "open_ft": "Fim de jogo em {venue}: {home} {hs}, {away} {as_}.", "open_live": "{minute} minutos em {venue}: {home} {hs}, {away} {as_}.",
        "goal": "{scorer} marca para {team} aos {minute} minutos{assist}.", "assist": ", com passe de {player}",
        "stats": "{team} criaram {xg} gols esperados contra {opp_xg}, com {poss}% de posse.",
        "story": "A história do jogo: {title}.", "why": "E o gol de que todos vão falar: {headline}.",
        "player": "{player}: {goals} gol(s), {touches} toques, velocidade máxima {kmh} km/h.",
        "close": "Cada número conferido com os dados do jogo. Jogo simulado.",
        "mine_win": "{club} vence {opp} por {score}!", "mine_draw": "{club} empata em {score} com {opp}.", "mine_loss": "{club} perde para {opp} por {score}.",
        "push_goal_title": "GOL: {home} {score} {away}", "push_goal_body": "{scorer} ({minute}')",
        "push_ft_title": "Fim de jogo: {home} {hs}-{as_} {away}", "push_ft_body": "Gols esperados {hxg}-{axg}. {story}",
        "clip_goal": "Gol: {player} ({minute}')", "clip_chance": "Chance: {player} ({minute}')", "clip_card": "Amarelo: {player} ({minute}')",
        "lt_goal": "{team} {score}", "cue_score": "PLACAR", "cue_goal": "CLIPE DO GOL", "cue_stats": "ESTATÍSTICA", "cue_story": "HISTÓRIA", "cue_why": "POR QUE ACONTECEU", "cue_player": "JOGADOR",
        "card_xg": "Gols esperados", "card_shots": "Finalizações (no gol)", "card_poss": "Posse de bola",
        "thread_goals": "Gols: {list}.", "simulated": "Jogo simulado",
    },
    "ar": {
        "open_ft": "نهاية المباراة في {venue}: {home} {hs}، {away} {as_}.", "open_live": "الدقيقة {minute} في {venue}: {home} {hs}، {away} {as_}.",
        "goal": "{scorer} يسجل لـ {team} في الدقيقة {minute}{assist}.", "assist": "، بتمريرة من {player}",
        "stats": "صنع {team} {xg} من الأهداف المتوقعة مقابل {opp_xg}، مع استحواذ بنسبة {poss}%.",
        "story": "قصة المباراة: {title}.", "why": "والهدف الذي سيتحدث عنه الجميع: {headline}.",
        "player": "{player}: {goals} هدف، {touches} لمسة، أقصى سرعة {kmh} كم/س.",
        "close": "كل رقم تم التحقق منه من بيانات المباراة. مباراة محاكاة.",
        "mine_win": "{club} يفوز على {opp} {score}!", "mine_draw": "{club} يتعادل مع {opp} {score}.", "mine_loss": "{club} يخسر أمام {opp} {score}.",
        "push_goal_title": "هدف: {home} {score} {away}", "push_goal_body": "{scorer} (الدقيقة {minute})",
        "push_ft_title": "نهاية المباراة: {home} {hs}-{as_} {away}", "push_ft_body": "الأهداف المتوقعة {hxg}-{axg}. {story}",
        "clip_goal": "هدف: {player} (الدقيقة {minute})", "clip_chance": "فرصة: {player} (الدقيقة {minute})", "clip_card": "إنذار: {player} (الدقيقة {minute})",
        "lt_goal": "{team} {score}", "cue_score": "النتيجة", "cue_goal": "لقطة الهدف", "cue_stats": "رسم إحصائي", "cue_story": "القصة", "cue_why": "لماذا حدث", "cue_player": "بطاقة اللاعب",
        "card_xg": "الأهداف المتوقعة", "card_shots": "التسديدات (على المرمى)", "card_poss": "الاستحواذ",
        "thread_goals": "الأهداف: {list}.", "simulated": "مباراة محاكاة",
    },
}

CLIP = {"goal": (25, 10), "big_chance": (15, 6), "card": (8, 6)}
HIGHLIGHTS_MAX_S = 180  # a two-to-three-minute package


def timecode(seconds: float) -> str:
    s = max(0.0, seconds)
    frames = int(round(s * FPS))
    return f"{frames // (3600 * FPS):02d}:{frames // (60 * FPS) % 60:02d}:{frames // FPS % 60:02d}:{frames % FPS:02d}"


def build_pack(match: dict, timeline: dict, narrative: dict, lang: str = "en", *, explanation: dict | None = None,
               club: str | None = None, player: str | None = None) -> dict:
    """`timeline` and `narrative` are already in `lang`; `explanation` is the featured goal's checked AI explanation."""
    tx = P.get(lang, P["en"])
    home, away = match["home"], match["away"]
    names = {home: match["home_name"], away: match["away_name"]}
    roster = match["roster"]
    pname = lambda pid: roster.get(pid, {}).get("name", "") if pid else ""  # noqa: E731
    states = timeline["states"]
    last = states[-1] if states else None
    finished = bool(last and last["minute"] >= 90)
    g = {t: (last["teams"][t]["goals"] if last else 0) for t in (home, away)}
    venue = match.get("metadata", {}).get("venue") or ""
    moments = timeline["moments"]
    goals = [m for m in moments if m["type"] == "goal"]
    score_line = {"home": names[home], "away": names[away], "hs": g[home], "as_": g[away]}

    # --- presenter ---------------------------------------------------------------------------------------
    def line(cue: str, text: str) -> dict:
        return {"cue": tx[cue], "text": text}

    opening = tx["open_ft" if finished else "open_live"].format(minute=last["minute"] if last else 0, venue=venue or "—", **score_line)
    if club in (home, away):
        opp = away if club == home else home
        res = "mine_win" if g[club] > g[opp] else "mine_draw" if g[club] == g[opp] else "mine_loss"
        opening = tx[res].format(club=names[club], opp=names[opp], score=f"{g[club]}-{g[opp]}") + " " + opening
    goal_lines = [line("cue_goal", tx["goal"].format(scorer=pname(m["player_id"]), team=names[m["team"]], minute=m["minute"],
                                                      assist=tx["assist"].format(player=pname(m.get("assist_id"))) if m.get("assist_id") else ""))
                  for m in goals]
    stats_lines = []
    if last:
        lead = home if last["teams"][home]["xg"] >= last["teams"][away]["xg"] else away
        o = away if lead == home else home
        stats_lines.append(line("cue_stats", tx["stats"].format(team=names[lead], xg=f"{last['teams'][lead]['xg']:.2f}",
                                                                 opp_xg=f"{last['teams'][o]['xg']:.2f}", poss=last["teams"][lead]["possession"])))
    stories = sorted(narrative.get("storylines", []), key=lambda s: (-len(s["beats"]), s["opened_t"]))
    story_lines = [line("cue_story", tx["story"].format(title=s["title"].rstrip("?!.")) + " " + s["beats"][-1]["text"]) for s in stories[:2]]
    why_line = [line("cue_why", tx["why"].format(headline=explanation["headline"].rstrip("."))) ] if explanation and explanation.get("headline") else []
    player_line = []
    if player in timeline.get("players", {}):
        p = timeline["players"][player]
        player_line = [line("cue_player", tx["player"].format(player=p["name"], goals=p["goals"], touches=p["touches"], kmh=p["top_speed_kmh"]))]
    close = [line("cue_score", tx["close"])]
    key_goals = goal_lines if len(goal_lines) <= 4 else goal_lines[:2] + goal_lines[-2:]
    short = [line("cue_score", opening)] + key_goals + (why_line or story_lines[:1]) + player_line[:1] + close
    long = [line("cue_score", opening)] + goal_lines + stats_lines + story_lines + why_line + player_line + close

    def script(lines: list) -> dict:
        words = sum(len(x["text"].split()) for x in lines)
        return {"lines": lines, "words": words, "seconds": round(words / WORDS_PER_SECOND)}

    # --- highlights rundown ----------------------------------------------------------------------------
    candidates = [m for m in moments if m["type"] in CLIP]
    candidates.sort(key=lambda m: (-(m["type"] == "goal"), -m.get("importance", 0), -(m.get("xg") or 0)))
    chosen, total = [], 0.0
    for m in candidates:
        pre, post = CLIP[m["type"]]
        length = pre + post
        if m["type"] != "goal" and total + length > HIGHLIGHTS_MAX_S:
            continue
        chosen.append(m)
        total += length
    chosen.sort(key=lambda m: m["t"])
    clips = []
    for m in chosen:
        pre, post = CLIP[m["type"]]
        t_in, t_out = max(0.0, m["t"] - pre), m["t"] + post
        if clips and t_in <= clips[-1]["out"]:  # overlapping: extend the previous clip
            clips[-1]["out"] = round(t_out, 1)
            clips[-1]["out_tc"] = timecode(t_out)
            clips[-1]["label"] += " + " + _clip_label(tx, m, pname)
            continue
        clips.append({"n": len(clips) + 1, "type": m["type"], "minute": m["minute"], "team": m["team"],
                      "in": round(t_in, 1), "out": round(t_out, 1), "in_tc": timecode(t_in), "out_tc": timecode(t_out),
                      "label": _clip_label(tx, m, pname), "why": m.get("why", ""),
                      "for_you": bool((club and m["team"] == club) or (player and player in (m.get("player_id"), m.get("assist_id"))))})
    for i, c in enumerate(clips, 1):
        c["n"] = i
    duration = round(sum(c["out"] - c["in"] for c in clips), 1)

    # --- lower thirds, push, social, stat cards ---------------------------------------------------------
    top = sorted([m for m in moments if m["type"] != "pass"], key=lambda m: -m.get("importance", 0))[:8]
    lower_thirds = [{"t": m["t"], "minute": m["minute"], "team": m["team"], "line1": m["headline"], "line2": m["why"]}
                    for m in sorted(top, key=lambda m: m["t"])]
    push = [{"t": m["t"], "minute": m["minute"], "title": tx["push_goal_title"].format(home=names[home], away=names[away], score=m.get("score", "")),
             "body": tx["push_goal_body"].format(scorer=pname(m["player_id"]), minute=m["minute"]),
             "for_you": bool((club and m["team"] == club) or (player and player in (m.get("player_id"), m.get("assist_id"))))}
            for m in goals]
    story_text = stories[0]["title"] if stories else ""
    if finished and last:
        push.append({"t": last["minute"] * 60, "minute": last["minute"], "title": tx["push_ft_title"].format(**score_line),
                     "body": tx["push_ft_body"].format(hxg=f"{last['teams'][home]['xg']:.2f}", axg=f"{last['teams'][away]['xg']:.2f}",
                                                       story=story_text).strip(), "for_you": bool(club)})
    tags = " ".join("#" + "".join(ch for ch in names[t].title() if ch.isalnum()) for t in (home, away))
    head = opening if club in (home, away) else tx["open_ft" if finished else "open_live"].format(
        minute=last["minute"] if last else 0, venue=venue or "—", **score_line)
    post = f"{head} {stories[0]['title'] if stories else ''}".strip()
    post = (post[: 280 - len(tags) - 2].rstrip() + " " + tags) if len(post) + len(tags) + 1 > 280 else f"{post} {tags}"
    goal_list = ", ".join(f"{pname(m['player_id'])} {m['minute']}'" for m in goals)
    thread = [head, tx["thread_goals"].format(list=goal_list or "—")] + [x["text"] for x in stats_lines + story_lines[:1] + why_line]
    stat_cards = []
    if last:
        tl_ = last["teams"]
        stat_cards = [
            {"title": tx["card_xg"], "home": f"{tl_[home]['xg']:.2f}", "away": f"{tl_[away]['xg']:.2f}"},
            {"title": tx["card_shots"], "home": f"{tl_[home]['shots']} ({tl_[home]['on_target']})", "away": f"{tl_[away]['shots']} ({tl_[away]['on_target']})"},
            {"title": tx["card_poss"], "home": f"{tl_[home]['possession']}%", "away": f"{tl_[away]['possession']}%"},
        ]
    return {
        "schema": "beyond-the-replay/studio-pack", "version": "1.0", "lang": lang, "simulated": True, "finished": finished,
        "match": {"home": home, "away": away, "home_name": names[home], "away_name": names[away], "score": g,
                  "venue": venue, "minute": last["minute"] if last else 0},
        "personal": {"club": club, "player": player},
        "presenter": {"30s": script(short), "60s": script(long)},
        "highlights": {"clips": clips, "duration_s": duration, "fps": FPS, "timecode": "match clock from kick-off"},
        "lower_thirds": lower_thirds, "push": push,
        "social": {"post": post, "thread": thread, "caption": "\n".join([head] + [x["text"] for x in goal_lines] + [tags, tx["simulated"]])},
        "stat_cards": stat_cards,
        "why_it_happened": {"headline": explanation["headline"], "confidence": explanation.get("confidence")} if why_line else None,
    }


def _clip_label(tx: dict, m: dict, pname) -> str:
    key = {"goal": "clip_goal", "big_chance": "clip_chance", "card": "clip_card"}[m["type"]]
    return tx[key].format(player=pname(m.get("player_id")), minute=m["minute"])


def to_edl(pack: dict, title: str = "BEYOND THE REPLAY HIGHLIGHTS") -> str:
    """CMX3600 edit decision list: source = the match feed from kick-off, record = the highlights reel."""
    out = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for c in pack["highlights"]["clips"]:
        length = c["out"] - c["in"]
        out.append(f"{c['n']:03d}  AX       V     C        {c['in_tc']} {c['out_tc']} {timecode(rec)} {timecode(rec + length)}")
        out.append(f"* FROM CLIP NAME: {c['label']}")
        rec += length
    return "\n".join(out) + "\n"


def to_csv(pack: dict) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["clip", "type", "minute", "in", "out", "in_tc", "out_tc", "label", "for_you"])
    for c in pack["highlights"]["clips"]:
        w.writerow([c["n"], c["type"], c["minute"], c["in"], c["out"], c["in_tc"], c["out_tc"], c["label"], c["for_you"]])
    return buf.getvalue()


def to_markdown(pack: dict) -> str:
    m = pack["match"]
    lines = [f"# {m['home_name']} {m['score'][m['home']]}-{m['score'][m['away']]} {m['away_name']}", "",
             f"*{m['venue']} · simulated match · studio pack v{pack['version']} ({pack['lang']})*", ""]
    for key in ("30s", "60s"):
        s = pack["presenter"][key]
        lines += [f"## Presenter script, {key} ({s['words']} words, about {s['seconds']} s)", ""]
        lines += [f"- **[{x['cue']}]** {x['text']}" for x in s["lines"]] + [""]
    lines += [f"## Highlights ({pack['highlights']['duration_s']} s)", "", "| # | In | Out | Clip |", "|---|---|---|---|"]
    lines += [f"| {c['n']} | {c['in_tc']} | {c['out_tc']} | {c['label']} |" for c in pack["highlights"]["clips"]] + [""]
    lines += ["## Social", "", pack["social"]["post"], ""]
    lines += ["## Push alerts", ""] + [f"- **{p['title']}** {p['body']}" for p in pack["push"]] + [""]
    lines += ["## Lower thirds", ""] + [f"- {x['minute']}' **{x['line1']}**: {x['line2']}" for x in pack["lower_thirds"]] + [""]
    return "\n".join(lines)
