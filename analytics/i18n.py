"""On-screen text in five languages, rendered deterministically from structured moments and cues.

Overlay graphics need to be instant and exactly right, so they use fixed, human-written phrasing
per language rather than a model. Names and numbers are inserted unchanged. Recaps (longer prose)
are written by Claude separately and fact-checked.
"""
from __future__ import annotations

import copy

LANGUAGES = {"en": "English", "es": "Español", "fr": "Français", "pt": "Português (Brasil)", "ar": "العربية"}
RTL = {"ar"}

M = {
    "en": {
        "goal": "GOAL: {scorer}", "goal_assist": "GOAL: {scorer}, assisted by {assist}",
        "goal_big": "A {xg} xG chance: a big chance taken.", "goal_low": "A {xg} xG chance: a low-probability finish.",
        "chance_saved": "Big chance: {player} is denied", "chance_missed": "Big chance: {player} misses",
        "chance_why": "Worth {xg} expected goals: chances like it are scored about {pct}% of the time.",
        "card": "Yellow card: {player}", "card_why": "A booked player has to be more careful in every duel from here.",
        "momentum_take": "{team} take control", "momentum_turn": "{team} turn the tide",
        "momentum_why": "They have created clearly more threat than their opponents over the last ten minutes.",
        "pass": "{player} finds {receiver} with a {dist} m pass",
        "pass_why": "Rated {diff}/100 for difficulty: most passes like it don't arrive.",
        "tag_distance": "{player}: {value} m carried with the ball", "tag_speed": "{player}: {value} km/h",
        "tag_shot": "Shot speed: {value} km/h",
    },
    "es": {
        "goal": "GOL: {scorer}", "goal_assist": "GOL: {scorer}, con asistencia de {assist}",
        "goal_big": "Una ocasión de {xg} xG: una gran ocasión aprovechada.", "goal_low": "Una ocasión de {xg} xG: una definición improbable.",
        "chance_saved": "Gran ocasión: {player} no puede superar al portero", "chance_missed": "Gran ocasión: {player} falla",
        "chance_why": "Vale {xg} goles esperados: ocasiones así acaban en gol alrededor del {pct}% de las veces.",
        "card": "Tarjeta amarilla: {player}", "card_why": "Un jugador amonestado debe tener más cuidado en cada duelo a partir de ahora.",
        "momentum_take": "{team} toma el control", "momentum_turn": "{team} le da la vuelta al partido",
        "momentum_why": "Ha generado claramente más peligro que su rival en los últimos diez minutos.",
        "pass": "{player} encuentra a {receiver} con un pase de {dist} m",
        "pass_why": "Dificultad {diff}/100: la mayoría de pases así no llegan.",
        "tag_distance": "{player}: {value} m conduciendo el balón", "tag_speed": "{player}: {value} km/h",
        "tag_shot": "Velocidad del disparo: {value} km/h",
    },
    "fr": {
        "goal": "BUT : {scorer}", "goal_assist": "BUT : {scorer}, sur une passe de {assist}",
        "goal_big": "Une occasion à {xg} xG : une grosse occasion convertie.", "goal_low": "Une occasion à {xg} xG : une finition improbable.",
        "chance_saved": "Grosse occasion : {player} est repoussé", "chance_missed": "Grosse occasion : {player} manque le cadre",
        "chance_why": "Vaut {xg} buts attendus : ce genre d'occasion est converti environ {pct} % du temps.",
        "card": "Carton jaune : {player}", "card_why": "Un joueur averti doit désormais être plus prudent dans chaque duel.",
        "momentum_take": "{team} prend le contrôle", "momentum_turn": "{team} renverse la tendance",
        "momentum_why": "L'équipe s'est créé nettement plus de danger que son adversaire sur les dix dernières minutes.",
        "pass": "{player} trouve {receiver} d'une passe de {dist} m",
        "pass_why": "Difficulté {diff}/100 : la plupart des passes de ce type n'arrivent pas.",
        "tag_distance": "{player} : {value} m balle au pied", "tag_speed": "{player} : {value} km/h",
        "tag_shot": "Vitesse de frappe : {value} km/h",
    },
    "pt": {
        "goal": "GOL: {scorer}", "goal_assist": "GOL: {scorer}, com assistência de {assist}",
        "goal_big": "Uma chance de {xg} xG: uma grande chance aproveitada.", "goal_low": "Uma chance de {xg} xG: uma finalização improvável.",
        "chance_saved": "Grande chance: {player} para no goleiro", "chance_missed": "Grande chance: {player} desperdiça",
        "chance_why": "Vale {xg} gols esperados: chances assim viram gol em cerca de {pct}% das vezes.",
        "card": "Cartão amarelo: {player}", "card_why": "Um jogador advertido tem de ter mais cuidado em cada duelo a partir de agora.",
        "momentum_take": "{team} assume o controle", "momentum_turn": "{team} vira o jogo",
        "momentum_why": "Criou claramente mais perigo do que o adversário nos últimos dez minutos.",
        "pass": "{player} encontra {receiver} com um passe de {dist} m",
        "pass_why": "Dificuldade {diff}/100: a maioria dos passes assim não chega.",
        "tag_distance": "{player}: {value} m com a bola", "tag_speed": "{player}: {value} km/h",
        "tag_shot": "Velocidade do chute: {value} km/h",
    },
    "ar": {
        "goal": "هدف: {scorer}", "goal_assist": "هدف: {scorer}، بتمريرة من {assist}",
        "goal_big": "فرصة بقيمة {xg} xG: فرصة كبيرة استُغلت.", "goal_low": "فرصة بقيمة {xg} xG: إنهاء صعب الاحتمال.",
        "chance_saved": "فرصة كبيرة: الحارس يتصدى لـ{player}", "chance_missed": "فرصة كبيرة: {player} يهدر",
        "chance_why": "قيمتها {xg} من الأهداف المتوقعة: فرص مماثلة تُسجَّل في نحو {pct}% من المرات.",
        "card": "بطاقة صفراء: {player}", "card_why": "على اللاعب المُنذَر أن يكون أكثر حذرًا في كل التحام من الآن.",
        "momentum_take": "{team} يفرض سيطرته", "momentum_turn": "{team} يقلب الموازين",
        "momentum_why": "صنع خطورة أكبر بوضوح من منافسه في آخر عشر دقائق.",
        "pass": "{player} يجد {receiver} بتمريرة طولها {dist} م",
        "pass_why": "صعوبة {diff}/100: معظم التمريرات المماثلة لا تصل.",
        "tag_distance": "{player}: {value} م بالكرة", "tag_speed": "{player}: {value} كم/س",
        "tag_shot": "سرعة التسديدة: {value} كم/س",
    },
}

UI_SCHEMA_VERSION = "1.0"


def t(lang: str, key: str, **args) -> str:
    return M.get(lang, M["en"]).get(key, M["en"][key]).format(**args)


def localize(tl: dict, match: dict, lang: str) -> dict:
    """A copy of the timeline whose moment and cue texts are in `lang`."""
    if lang not in M:
        raise ValueError(f"unsupported language {lang!r}")
    roster = match["roster"]
    names = {match["home"]: match["home_name"], match["away"]: match["away_name"]}
    n = lambda pid: roster.get(pid, {}).get("name", pid) if pid else ""
    out = copy.deepcopy(tl)
    for m in out["moments"]:
        kind = m["type"]
        if kind == "goal":
            m["headline"] = t(lang, "goal_assist", scorer=n(m["player_id"]), assist=n(m["assist_id"])) if m.get("assist_id") \
                else t(lang, "goal", scorer=n(m["player_id"]))
            m["why"] = t(lang, "goal_big" if m["xg"] >= 0.25 else "goal_low", xg=f"{m['xg']:.2f}")
        elif kind == "big_chance":
            m["headline"] = t(lang, "chance_saved" if m.get("outcome") == "saved" else "chance_missed", player=n(m["player_id"]))
            m["why"] = t(lang, "chance_why", xg=f"{m['xg']:.2f}", pct=round(m["xg"] * 100))
        elif kind == "card":
            m["headline"], m["why"] = t(lang, "card", player=n(m["player_id"])), t(lang, "card_why")
        elif kind == "momentum":
            m["headline"] = t(lang, f"momentum_{m.get('variant', 'turn')}", team=names[m["team"]])
            m["why"] = t(lang, "momentum_why")
        elif kind == "pass":
            m["headline"] = t(lang, "pass", player=n(m["player_id"]), receiver=n(m["receiver_id"]), dist=f"{m['distance_m']:.0f}")
            m["why"] = t(lang, "pass_why", diff=m["difficulty"])
    by_t = {(m["t"], m["type"]): m for m in out["moments"]}
    for c in out["cues"]:
        if c["kind"] in ("lower_third", "goal"):
            m = next((x for (tt, _), x in by_t.items() if tt == c["t_in"] and x["headline"]), None)
            if m:
                c["text"], c["subtext"] = m["headline"], m["why"]
        elif c.get("metric") == "distance_carried_m":
            c["text"] = t(lang, "tag_distance", player=c["player"], value=c["value"])
        elif c.get("metric") == "speed_kmh":
            c["text"] = t(lang, "tag_speed", player=c["player"], value=f"{c['value']:.1f}")
        elif c.get("metric") == "shot_speed_kmh":
            c["text"] = t(lang, "tag_shot", value=f"{c['value']:.0f}")
    out["lang"] = lang
    out["dir"] = "rtl" if lang in RTL else "ltr"
    return out


def to_webvtt(cues: list, lang: str) -> str:
    """WebVTT metadata track: one cue per overlay, payload as JSON, for players that support timed metadata."""
    import json

    def ts(sec: float) -> str:
        h, rem = divmod(max(sec, 0), 3600)
        mnt, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(mnt):02d}:{s:06.3f}"

    lines = ["WEBVTT", f"Kind: metadata", f"Language: {lang}", ""]
    for i, c in enumerate(cues, 1):
        lines += [f"overlay-{i}", f"{ts(c['t_in'])} --> {ts(c['t_out'])}", json.dumps(c, ensure_ascii=False), ""]
    return "\n".join(lines)
