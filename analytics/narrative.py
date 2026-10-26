"""Real-time narratives: storylines that open, develop and resolve as the match unfolds, milestones, and a
"story so far" every fifteen minutes.

Single moments say what just happened; storylines say what is building. Each storyline is a thread with a
title fixed when it opens and dated beats added as evidence arrives:

  control     a side has been on top for a sustained spell (shots, threat), and whether it paid off;
  flank       one side keeps attacking down the same flank, and which defender is facing it;
  duels       a defender is losing far more one-on-ones than earlier in the match: are they tiring?;
  discipline  a booked player keeps committing fouls;
  chase       a trailing side is creating more than the leader, until they level or time runs out.

Everything is causal: a beat at minute m only uses events up to m, so the same function serves the live feed
(events so far) and replays (beats shown as the clock passes). Text is rendered from message keys in five
languages; names and numbers are inserted unchanged.
"""
from __future__ import annotations

from collections import defaultdict

from phase0.engine import PITCH_X, lane_of

from .models import attacks_right

SPELL_MOMENTUM = 0.6     # same threshold as a momentum moment
SPELL_MIN = 8            # minutes on top (with more shots than the opponent) before it is a storyline
FLANK_WINDOW = 15 * 60
FLANK_SHARE = 0.6
FLANK_MIN_ENTRIES = 12
DUEL_WINDOW = 10 * 60
SUMMARY_MINUTES = (15, 30, 45, 60, 75, 90)
PASS_MILESTONES = (100, 200, 300, 400)
XG_MILESTONES = (1.0, 2.0, 3.0)
FULL_BACK = {"left": "RB", "right": "LB"}  # the defender who faces an attack down that lane

T = {
    "en": {
        "control_title": "{team} on top", "control_open": "{team} have had the better of the last {n} minutes: {shots} shots to {opp_shots}.",
        "control_goal": "The pressure pays off: {player} scores.", "control_end": "{team}'s spell ends after {n} minutes{paid}.",
        "control_paid": ", with {goals} goal(s) to show for it", "control_unpaid": " without a goal",
        "flank_title": "{team} keep coming down the {lane}", "flank_beat": "{share}% of their attacks in the last 15 minutes went down the {lane}{at}.",
        "flank_at": ", straight at {player}",
        "duel_title": "Is {player} tiring?", "duel_beat": "{player} has lost {lost} of the last {n} one-on-ones, after losing {lost0} of {n0} before.",
        "duel_end": "{player} steadies: {won} of the last {n} one-on-ones won.",
        "card_title": "{player} on a yellow", "card_open": "Booked at {minute}'. One more mistimed challenge and {team} are down to ten.",
        "card_foul": "{player} commits another foul while on a yellow ({minute}').",
        "chase_title": "{team} chasing the game", "chase_beat": "{team} trail {score} but have {xg} xG in the last 15 minutes to {opp_xg}.",
        "chase_level": "{player} levels it at {minute}'!", "chase_fail": "Not enough: {team} could not find the equaliser.",
        "lane_left": "left", "lane_right": "right", "lane_center": "middle",
        "m_first_goal": "{player} opens the scoring for {team}", "m_brace": "{player} has two", "m_hattrick": "Hat-trick for {player}!",
        "m_passes": "{team} complete pass number {n}", "m_xg": "{team} pass {n} expected goals",
        "m_shots": "{team} reach 10 shots", "m_sprint": "{player} hits {kmh} km/h: the fastest sprint of the match so far",
        "sum_head": "{minute}': {home} {hs}-{as_} {away}.", "sum_ht": "Half-time: {home} {hs}-{as_} {away}.", "sum_ft": "Full-time: {home} {hs}-{as_} {away}.",
        "sum_on_top": "{team} have been on top over the last 15 minutes.", "sum_even": "Neither side has controlled the last 15 minutes.",
        "sum_stats": "Expected goals {hxg}-{axg}, possession {hp}%-{ap}%.", "sum_watch": "Watch: {title}.",
    },
    "es": {
        "control_title": "{team} dominan", "control_open": "{team} han sido mejores en los últimos {n} minutos: {shots} tiros por {opp_shots}.",
        "control_goal": "La presión da frutos: marca {player}.", "control_end": "Termina el dominio de {team} tras {n} minutos{paid}.",
        "control_paid": ", con {goals} gol(es) en ese tramo", "control_unpaid": " sin gol",
        "flank_title": "{team} insisten por la {lane}", "flank_beat": "El {share}% de sus ataques en los últimos 15 minutos fue por la {lane}{at}.",
        "flank_at": ", directo hacia {player}",
        "duel_title": "¿Se está cansando {player}?", "duel_beat": "{player} ha perdido {lost} de los últimos {n} duelos, tras perder {lost0} de {n0} antes.",
        "duel_end": "{player} se recompone: gana {won} de los últimos {n} duelos.",
        "card_title": "{player}, amonestado", "card_open": "Amarilla en el {minute}'. Una entrada más a destiempo y {team} se quedan con diez.",
        "card_foul": "{player} vuelve a cometer falta con amarilla ({minute}').",
        "chase_title": "{team} persiguen el partido", "chase_beat": "{team} pierden {score}, pero suman {xg} xG en los últimos 15 minutos por {opp_xg}.",
        "chase_level": "¡{player} empata en el {minute}'!", "chase_fail": "No alcanzó: {team} no encontraron el empate.",
        "lane_left": "izquierda", "lane_right": "derecha", "lane_center": "zona central",
        "m_first_goal": "{player} abre el marcador para {team}", "m_brace": "Doblete de {player}", "m_hattrick": "¡Triplete de {player}!",
        "m_passes": "{team} completan su pase número {n}", "m_xg": "{team} superan {n} goles esperados",
        "m_shots": "{team} llegan a 10 tiros", "m_sprint": "{player} alcanza {kmh} km/h: el sprint más rápido del partido hasta ahora",
        "sum_head": "{minute}': {home} {hs}-{as_} {away}.", "sum_ht": "Descanso: {home} {hs}-{as_} {away}.", "sum_ft": "Final: {home} {hs}-{as_} {away}.",
        "sum_on_top": "{team} han dominado los últimos 15 minutos.", "sum_even": "Ningún equipo ha dominado los últimos 15 minutos.",
        "sum_stats": "Goles esperados {hxg}-{axg}, posesión {hp}%-{ap}%.", "sum_watch": "Atención: {title}.",
    },
    "fr": {
        "control_title": "{team} dominent", "control_open": "{team} ont été meilleurs ces {n} dernières minutes : {shots} tirs contre {opp_shots}.",
        "control_goal": "La pression paie : {player} marque.", "control_end": "Fin de la domination de {team} après {n} minutes{paid}.",
        "control_paid": ", avec {goals} but(s) à la clé", "control_unpaid": " sans but",
        "flank_title": "{team} insistent côté {lane}", "flank_beat": "{share} % de leurs attaques des 15 dernières minutes sont passées côté {lane}{at}.",
        "flank_at": ", droit sur {player}",
        "duel_title": "{player} fatigue-t-il ?", "duel_beat": "{player} a perdu {lost} de ses {n} derniers duels, contre {lost0} sur {n0} avant.",
        "duel_end": "{player} se reprend : {won} des {n} derniers duels gagnés.",
        "card_title": "{player} sous la menace", "card_open": "Averti à la {minute}'. Encore une intervention ratée et {team} seront à dix.",
        "card_foul": "{player} commet une nouvelle faute alors qu'il est averti ({minute}').",
        "chase_title": "{team} courent après le score", "chase_beat": "{team} sont menés {score} mais ont {xg} xG sur les 15 dernières minutes contre {opp_xg}.",
        "chase_level": "{player} égalise à la {minute}' !", "chase_fail": "Pas suffisant : {team} n'ont pas trouvé l'égalisation.",
        "lane_left": "gauche", "lane_right": "droit", "lane_center": "axe",
        "m_first_goal": "{player} ouvre le score pour {team}", "m_brace": "Doublé pour {player}", "m_hattrick": "Triplé pour {player} !",
        "m_passes": "{team} réussissent leur passe numéro {n}", "m_xg": "{team} dépassent {n} buts attendus",
        "m_shots": "{team} atteignent 10 tirs", "m_sprint": "{player} atteint {kmh} km/h : le sprint le plus rapide du match jusqu'ici",
        "sum_head": "{minute}' : {home} {hs}-{as_} {away}.", "sum_ht": "Mi-temps : {home} {hs}-{as_} {away}.", "sum_ft": "Fin du match : {home} {hs}-{as_} {away}.",
        "sum_on_top": "{team} ont dominé les 15 dernières minutes.", "sum_even": "Aucune équipe n'a dominé les 15 dernières minutes.",
        "sum_stats": "Buts attendus {hxg}-{axg}, possession {hp} %-{ap} %.", "sum_watch": "À suivre : {title}.",
    },
    "pt": {
        "control_title": "{team} por cima", "control_open": "{team} foram melhores nos últimos {n} minutos: {shots} finalizações contra {opp_shots}.",
        "control_goal": "A pressão funciona: {player} marca.", "control_end": "Acaba o domínio de {team} após {n} minutos{paid}.",
        "control_paid": ", com {goals} gol(s) no período", "control_unpaid": " sem gol",
        "flank_title": "{team} insistem pela {lane}", "flank_beat": "{share}% dos ataques nos últimos 15 minutos foram pela {lane}{at}.",
        "flank_at": ", direto em cima de {player}",
        "duel_title": "{player} está cansando?", "duel_beat": "{player} perdeu {lost} dos últimos {n} duelos, depois de perder {lost0} de {n0} antes.",
        "duel_end": "{player} se recupera: venceu {won} dos últimos {n} duelos.",
        "card_title": "{player} pendurado", "card_open": "Amarelo aos {minute}'. Mais uma entrada atrasada e {team} ficam com dez.",
        "card_foul": "{player} comete outra falta já amarelado ({minute}').",
        "chase_title": "{team} correm atrás", "chase_beat": "{team} perdem por {score}, mas têm {xg} xG nos últimos 15 minutos contra {opp_xg}.",
        "chase_level": "{player} empata aos {minute}'!", "chase_fail": "Não deu: {team} não acharam o empate.",
        "lane_left": "esquerda", "lane_right": "direita", "lane_center": "faixa central",
        "m_first_goal": "{player} abre o placar para {team}", "m_brace": "{player} marca o segundo", "m_hattrick": "Hat-trick de {player}!",
        "m_passes": "{team} completam o passe número {n}", "m_xg": "{team} passam de {n} gols esperados",
        "m_shots": "{team} chegam a 10 finalizações", "m_sprint": "{player} chega a {kmh} km/h: o sprint mais rápido do jogo até agora",
        "sum_head": "{minute}': {home} {hs}-{as_} {away}.", "sum_ht": "Intervalo: {home} {hs}-{as_} {away}.", "sum_ft": "Fim de jogo: {home} {hs}-{as_} {away}.",
        "sum_on_top": "{team} dominaram os últimos 15 minutos.", "sum_even": "Nenhum time dominou os últimos 15 minutos.",
        "sum_stats": "Gols esperados {hxg}-{axg}, posse {hp}%-{ap}%.", "sum_watch": "De olho: {title}.",
    },
    "ar": {
        "control_title": "{team} يسيطر", "control_open": "{team} الأفضل في آخر {n} دقائق: {shots} تسديدات مقابل {opp_shots}.",
        "control_goal": "الضغط يثمر: {player} يسجل.", "control_end": "انتهت سيطرة {team} بعد {n} دقيقة{paid}.",
        "control_paid": " وحصيلتها {goals} هدف", "control_unpaid": " دون هدف",
        "flank_title": "{team} يواصل الهجوم من الجهة {lane}", "flank_beat": "{share}% من هجماته في آخر 15 دقيقة جاءت من الجهة {lane}{at}.",
        "flank_at": "، مباشرة نحو {player}",
        "duel_title": "هل بدأ {player} يتعب؟", "duel_beat": "خسر {player} {lost} من آخر {n} مواجهات فردية، بعد أن خسر {lost0} من {n0} قبل ذلك.",
        "duel_end": "{player} يستعيد توازنه: فاز في {won} من آخر {n} مواجهات.",
        "card_title": "{player} مهدد بالطرد", "card_open": "إنذار في الدقيقة {minute}. تدخل آخر متأخر وسيكمل {team} بعشرة لاعبين.",
        "card_foul": "{player} يرتكب خطأ جديدا رغم الإنذار (الدقيقة {minute}).",
        "chase_title": "{team} يطارد النتيجة", "chase_beat": "{team} متأخر {score} لكنه صنع {xg} من الأهداف المتوقعة في آخر 15 دقيقة مقابل {opp_xg}.",
        "chase_level": "{player} يعادل في الدقيقة {minute}!", "chase_fail": "لم يكن كافيا: {team} لم يجد هدف التعادل.",
        "lane_left": "اليسرى", "lane_right": "اليمنى", "lane_center": "الوسطى",
        "m_first_goal": "{player} يفتتح التسجيل لـ {team}", "m_brace": "ثنائية لـ {player}", "m_hattrick": "هاتريك لـ {player}!",
        "m_passes": "{team} يكمل التمريرة رقم {n}", "m_xg": "{team} يتجاوز {n} من الأهداف المتوقعة",
        "m_shots": "{team} يصل إلى 10 تسديدات", "m_sprint": "{player} يبلغ {kmh} كم/س: أسرع انطلاقة في المباراة حتى الآن",
        "sum_head": "الدقيقة {minute}: {home} {hs}-{as_} {away}.", "sum_ht": "نهاية الشوط الأول: {home} {hs}-{as_} {away}.", "sum_ft": "نهاية المباراة: {home} {hs}-{as_} {away}.",
        "sum_on_top": "{team} كان الأفضل في آخر 15 دقيقة.", "sum_even": "لم يسيطر أي فريق في آخر 15 دقيقة.",
        "sum_stats": "الأهداف المتوقعة {hxg}-{axg}، الاستحواذ {hp}%-{ap}%.", "sum_watch": "تابع: {title}.",
    },
}


def _minute(t: float) -> int:
    return int(t // 60) + 1


def _progress(e: dict, home: str) -> float:
    return (e["x"] if attacks_right(e["team"], home) else PITCH_X - e["x"]) / PITCH_X


class _Story:
    def __init__(self, sid: str, kind: str, team: str, player_id: str | None, t: float, title: tuple):
        self.d = {"id": sid, "kind": kind, "team": team, "player_id": player_id, "opened_t": t, "status": "open",
                  "title": title, "beats": []}

    def beat(self, t: float, key: str, **params) -> None:
        self.d["beats"].append({"t": round(t, 1), "minute": _minute(t), "msg": key, "params": params})

    def close(self, t: float, key: str, **params) -> None:
        self.beat(t, key, **params)
        self.d["status"], self.d["closed_t"] = "resolved", round(t, 1)


def build_narrative(match: dict, timeline: dict, upto_t: float | None = None, final: bool = False) -> dict:
    """Storylines, milestones and summaries from the events received so far (or up to `upto_t`).
    Returns structures with message keys; `render()` turns them into text in a language."""
    home, away = match["home"], match["away"]
    roster = match["roster"]
    other = {home: away, away: home}
    events = [e for e in timeline["events"] if upto_t is None or e["t"] <= upto_t]
    states = [s for s in timeline["states"] if upto_t is None or s["minute"] * 60 <= upto_t]
    goals = [m for m in timeline["moments"] if m["type"] == "goal" and (upto_t is None or m["t"] <= upto_t)]
    end_t = events[-1]["t"] if events else 0.0
    stories: list[_Story] = []
    milestones: list[dict] = []

    def role_player(team: str, role: str) -> str | None:
        return next((pid for pid, p in roster.items() if p["team"] == team and p.get("role") == role), None)

    # --- control: sustained momentum spells -------------------------------------------------------------
    spell, open_story = None, None
    for s in states:
        side = home if s["momentum"] >= SPELL_MOMENTUM else away if s["momentum"] <= -SPELL_MOMENTUM else None
        if spell and side != spell["team"]:
            if open_story:
                n = s["minute"] - spell["start"]
                scored = sum(1 for g in goals if g["team"] == spell["team"] and spell["start"] * 60 <= g["t"] <= s["minute"] * 60)
                open_story.close(s["minute"] * 60, "control_end", team=spell["team"], n=n, goals=scored,
                                 paid=("control_paid", {"goals": scored}) if scored else "control_unpaid")
            spell, open_story = None, None
        if side and not spell:
            spell = {"team": side, "start": s["minute"]}
        if spell and not open_story and s["minute"] - spell["start"] + 1 >= SPELL_MIN:
            t0, t1 = spell["start"] * 60 - 60, s["minute"] * 60
            shots = sum(1 for e in events if e["type"] == "shot" and t0 <= e["t"] <= t1 and e["team"] == side)
            opp = sum(1 for e in events if e["type"] == "shot" and t0 <= e["t"] <= t1 and e["team"] == other[side])
            if shots < 2 or shots <= opp:  # territory without chances is not a story yet
                continue
            open_story = _Story(f"control-{side}-{spell['start']}", "control", side, None, t1, ("control_title", {"team": side}))
            open_story.beat(t1, "control_open", team=side, n=s["minute"] - spell["start"] + 1, shots=shots, opp_shots=opp)
            stories.append(open_story)
        if open_story:
            for g in goals:
                if g["team"] == spell["team"] and (s["minute"] - 1) * 60 < g["t"] <= s["minute"] * 60:
                    open_story.beat(g["t"], "control_goal", player=g["player_id"])

    # --- flank: attacks concentrated down one lane, checked every five minutes -------------------------
    entries = [(e["t"], e["team"], lane_of(e["y"], attacks_right(e["team"], home)))
               for e in events if e["type"] in ("pass", "carry", "dribble", "cross") and _progress(e, home) >= 0.66]
    flank_open: dict[str, _Story] = {}
    for minute in range(20, _minute(end_t) + 1, 5):
        t1 = minute * 60
        for team in (home, away):
            window = [x for x in entries if x[1] == team and t1 - FLANK_WINDOW < x[0] <= t1]
            if len(window) < FLANK_MIN_ENTRIES:
                continue
            for lane in ("left", "right"):
                share = sum(1 for x in window if x[2] == lane) / len(window)
                key = f"{team}-{lane}"
                if share >= FLANK_SHARE:
                    fb = role_player(other[team], FULL_BACK[lane])
                    st = flank_open.get(key)
                    if st is None:
                        st = _Story(f"flank-{key}-{minute}", "flank", team, fb, t1, ("flank_title", {"team": team, "lane": f"lane_{lane}"}))
                        flank_open[key] = st
                        stories.append(st)
                    last = st.d["beats"][-1]["params"]["share"] if st.d["beats"] else -100
                    if len(st.d["beats"]) < 4 and abs(round(share * 100) - last) >= 5:
                        st.beat(t1, "flank_beat", share=round(share * 100), lane=f"lane_{lane}",
                                at=("flank_at", {"player": fb}) if fb else "")
                elif key in flank_open and share < FLANK_SHARE - 0.1:
                    flank_open.pop(key).d["status"] = "resolved"

    # --- duels: a full-back losing far more one-on-ones than earlier -----------------------------------
    duels = defaultdict(list)  # defender -> [(t, won)]
    for e in events:
        if e["type"] == "dribble" and e.get("opponent_id"):
            duels[e["opponent_id"]].append((e["t"], e["outcome"] != "success"))
        elif e["type"] == "tackle":
            duels[e["player_id"]].append((e["t"], e["outcome"] == "success"))
    for pid, record in duels.items():
        if roster.get(pid, {}).get("role") not in ("RB", "LB", "CB1", "CB2"):
            continue
        st, last_beat = None, -1e9
        for minute in range(40, _minute(end_t) + 1):  # tiring is a second-half story
            t1 = minute * 60
            recent = [w for t, w in record if t1 - DUEL_WINDOW < t <= t1]
            before = [w for t, w in record if t <= t1 - DUEL_WINDOW]
            if len(recent) < 7 or len(before) < 20:
                continue
            lost, lost0 = sum(1 for w in recent if not w), sum(1 for w in before if not w)
            rate, rate0 = lost / len(recent), lost0 / len(before)
            if st is not None and st.d["status"] == "resolved" and t1 - st.d["closed_t"] >= 600:
                st = None  # a fresh decline later on is a new story
            if st is None and rate >= max(0.8, rate0 + 0.12):  # clearly worse than their own earlier level
                st = _Story(f"duels-{pid}-{minute}", "duels", roster[pid]["team"], pid, t1, ("duel_title", {"player": pid}))
                stories.append(st)
            if st is not None and st.d["status"] == "open":
                if rate >= max(0.75, rate0) and len(st.d["beats"]) < 3 and t1 - last_beat >= 300:
                    st.beat(t1, "duel_beat", player=pid, lost=lost, n=len(recent), lost0=lost0, n0=len(before))
                    last_beat = t1
                elif rate < rate0 - 0.1:
                    st.close(t1, "duel_end", player=pid, won=len(recent) - lost, n=len(recent))

    # --- discipline: booked players who keep fouling -----------------------------------------------------
    booked = {}
    for e in events:
        if e["type"] == "card" and e["player_id"] not in booked:
            st = _Story(f"card-{e['player_id']}-{_minute(e['t'])}", "discipline", e["team"], e["player_id"], e["t"],
                        ("card_title", {"player": e["player_id"]}))
            st.beat(e["t"], "card_open", minute=_minute(e["t"]), team=e["team"])
            booked[e["player_id"]] = st
            stories.append(st)
        elif e["type"] == "foul" and e["player_id"] in booked and e["t"] > booked[e["player_id"]].d["opened_t"] + 5:
            booked[e["player_id"]].beat(e["t"], "card_foul", player=e["player_id"], minute=_minute(e["t"]))

    # --- chase: a trailing side out-creating the leader -------------------------------------------------
    chase = None
    xg_events = [(e["t"], e["team"], e.get("xg") or 0.0) for e in events if e["type"] == "shot"]
    for s in states:
        if s["minute"] < 20 or s["minute"] % 5:
            continue
        g = {t: s["teams"][t]["goals"] for t in (home, away)}
        if g[home] == g[away]:
            if chase and chase.d["status"] == "open":
                leveller = next((m for m in goals if m["team"] == chase.d["team"] and m["t"] <= s["minute"] * 60
                                 and m["t"] > chase.d["opened_t"]), None)
                if leveller:
                    chase.close(leveller["t"], "chase_level", player=leveller["player_id"], minute=leveller["minute"])
            chase = None
            continue
        trailing = home if g[home] < g[away] else away
        t1 = s["minute"] * 60
        recent = {t: round(sum(x for tt, team, x in xg_events if team == t and t1 - 900 < tt <= t1), 2) for t in (home, away)}
        if recent[trailing] > recent[other[trailing]] + 0.3 and (chase is None or chase.d["team"] != trailing):
            chase = _Story(f"chase-{trailing}-{s['minute']}", "chase", trailing, None, t1, ("chase_title", {"team": trailing}))
            stories.append(chase)
        if chase and chase.d["team"] == trailing and chase.d["status"] == "open" and len(chase.d["beats"]) < 3                 and recent[trailing] > recent[other[trailing]]:
            chase.beat(t1, "chase_beat", team=trailing, score=f"{g[trailing]}-{g[other[trailing]]}",
                       xg=f"{recent[trailing]:.2f}", opp_xg=f"{recent[other[trailing]]:.2f}")
    if final and chase and chase.d["status"] == "open":
        chase.close(end_t, "chase_fail", team=chase.d["team"])

    # --- milestones ------------------------------------------------------------------------------------------
    scored = defaultdict(int)
    for i, g in enumerate(goals):
        scored[g["player_id"]] += 1
        n = scored[g["player_id"]]
        if i == 0:
            milestones.append({"key": "first-goal", "t": g["t"], "msg": "m_first_goal", "params": {"player": g["player_id"], "team": g["team"]}})
        if n in (2, 3):
            milestones.append({"key": f"goals-{g['player_id']}-{n}", "t": g["t"], "msg": "m_brace" if n == 2 else "m_hattrick",
                               "params": {"player": g["player_id"]}})
    passes, shots, xg_sum, top_speed = defaultdict(int), defaultdict(int), defaultdict(float), 0.0
    for e in events:
        team = e["team"]
        if e["type"] in ("pass", "cross") and e["outcome"] == "success":
            passes[team] += 1
            if passes[team] in PASS_MILESTONES:
                milestones.append({"key": f"passes-{team}-{passes[team]}", "t": e["t"], "msg": "m_passes", "params": {"team": team, "n": passes[team]}})
        if e["type"] == "shot":
            shots[team] += 1
            before = xg_sum[team]
            xg_sum[team] += e.get("xg") or 0.0
            if shots[team] == 10:
                milestones.append({"key": f"shots-{team}", "t": e["t"], "msg": "m_shots", "params": {"team": team}})
            for x in XG_MILESTONES:
                if before < x <= xg_sum[team]:
                    milestones.append({"key": f"xg-{team}-{x}", "t": e["t"], "msg": "m_xg", "params": {"team": team, "n": f"{x:.1f}"}})
        speed = e.get("speed_kmh") or 0.0
        if e["type"] in ("carry", "dribble") and speed >= 33 and speed > top_speed + 0.5 and e["t"] > 600:
            milestones.append({"key": f"sprint-{e['id']}", "t": e["t"], "msg": "m_sprint", "params": {"player": e["player_id"], "kmh": f"{speed:.1f}"}})
        if e["type"] in ("carry", "dribble"):
            top_speed = max(top_speed, speed)
    milestones.sort(key=lambda m: m["t"])

    # --- story so far ------------------------------------------------------------------------------------------
    summaries = []
    by_minute = {s["minute"]: s for s in states}
    for minute in SUMMARY_MINUTES:
        s = by_minute.get(minute)
        if s is None or (minute == 90 and not final and upto_t is None and end_t < 90 * 60):
            continue
        t1 = minute * 60
        recent_m = [x["momentum"] for x in states if t1 - 900 < x["minute"] * 60 <= t1]
        avg = sum(recent_m) / len(recent_m) if recent_m else 0.0
        live = [st for st in stories if st.d["opened_t"] <= t1 and (st.d["status"] == "open" or st.d.get("closed_t", 1e9) > t1)]
        live.sort(key=lambda st: (-len([b for b in st.d["beats"] if b["t"] <= t1]), -st.d["opened_t"]))
        summaries.append({"key": f"sum-{minute}", "t": t1, "minute": minute,
                          "phase": "ht" if minute == 45 else "ft" if minute == 90 else "live",
                          "on_top": home if avg >= 0.2 else away if avg <= -0.2 else None,
                          "score": {t: s["teams"][t]["goals"] for t in (home, away)},
                          "xg": {t: s["teams"][t]["xg"] for t in (home, away)},
                          "possession": {t: s["teams"][t]["possession"] for t in (home, away)},
                          "watch": live[0].d["title"] if live else None})
    return {"storylines": [st.d for st in sorted(stories, key=lambda st: st.d["opened_t"])],
            "milestones": milestones, "summaries": summaries, "home": home, "away": away}


def render(narrative: dict, match: dict, lang: str) -> dict:
    """Text for every storyline beat, milestone and summary in `lang` (names from the match sheet)."""
    tx = T.get(lang, T["en"])
    roster = match["roster"]
    names = {match["home"]: match["home_name"], match["away"]: match["away_name"]}

    def arg(v):
        if isinstance(v, tuple):  # a nested message, e.g. ("flank_at", {"player": ...})
            return fmt(*v)
        if isinstance(v, str) and v in tx:
            return tx[v]
        if isinstance(v, str) and v in names:
            return names[v]
        if isinstance(v, str) and v in roster:
            return roster[v]["name"]
        return v

    def fmt(key: str, params: dict) -> str:
        return tx[key].format(**{k: arg(v) for k, v in params.items()})

    out = {"storylines": [], "milestones": [], "summaries": []}
    for st in narrative["storylines"]:
        title_key, title_params = st["title"]
        out["storylines"].append({k: v for k, v in st.items() if k not in ("title", "beats")}
                                 | {"title": fmt(title_key, title_params),
                                    "beats": [{"t": b["t"], "minute": b["minute"], "text": fmt(b["msg"], b["params"])} for b in st["beats"]]})
    for m in narrative["milestones"]:
        out["milestones"].append({"key": m["key"], "t": m["t"], "minute": _minute(m["t"]), "kind": m["msg"], "text": fmt(m["msg"], m["params"])})
    home, away = narrative["home"], narrative["away"]
    for s in narrative["summaries"]:
        head = {"ht": "sum_ht", "ft": "sum_ft"}.get(s["phase"], "sum_head")
        parts = [fmt(head, {"minute": s["minute"], "home": home, "away": away, "hs": s["score"][home], "as_": s["score"][away]}),
                 fmt("sum_on_top", {"team": s["on_top"]}) if s["on_top"] else tx["sum_even"],
                 fmt("sum_stats", {"hxg": f"{s['xg'][home]:.2f}", "axg": f"{s['xg'][away]:.2f}",
                                   "hp": s["possession"][home], "ap": s["possession"][away]})]
        if s["watch"]:
            parts.append(fmt("sum_watch", {"title": fmt(*s["watch"]).rstrip("?!")}).replace("..", "."))
        out["summaries"].append({"key": s["key"], "t": s["t"], "minute": s["minute"], "phase": s["phase"], "text": " ".join(parts)})
    return out
