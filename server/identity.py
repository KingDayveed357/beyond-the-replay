"""Broadcast-safe identity: fictional clubs, players, stadiums and officials over the same simulated matches.

The matches are simulated from real 2024/25 squad strengths. Club names, stadiums and player names belong to
other people, and the hackathon rules forbid third-party trademarks in the demo, so every public output goes
through `identity().skin()` at the API boundary. Internally nothing changes: the engine, the saved AI
investigations, their cache keys and the answer key all keep working on the original data, so switching
identity costs no model calls.

BTR_NAMES=fictional (default) or real. `Identity.leaks()` is the compliance check: it scans any output for a
real club, stadium, nickname, player, manager or referee name, in Latin or Arabic script.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

LEAGUE_FILE = Path(__file__).resolve().parent.parent / "data" / "league" / "pl_2024_25.json"

# real code: (fictional code, name, short name, stadium, nickname, real alternative names, real nicknames)
CLUBS = {
    "ARS": ("ASR", "Ashridge Royal", "Ashridge", "Royal Gate", "Kestrels", [], ["Gunners"]),
    "AVL": ("HLM", "Hollowmere", "Hollowmere", "Mere Park", "Lions", ["Villa"], ["Villans"]),
    "BOU": ("SCF", "Saltcliffe", "Saltcliffe", "Cliffside Ground", "Gulls", [], ["Cherries"]),
    "BRE": ("BKV", "Brookvale", "Brookvale", "Vale Road", "Kingfishers", [], ["Bees"]),
    "BHA": ("SBR", "Seabright Albion", "Seabright", "The Pavilion", "Terns", ["Brighton"], ["Seagulls"]),
    "CHE": ("RVT", "Riverton", "Riverton", "Embankment Park", "Ravens", [], ["Blues", "Pensioners"]),
    "CRY": ("GLH", "Glasshill", "Glasshill", "Glasshill Park", "Falcons", ["Palace"], ["Eagles"]),
    "EVE": ("DKS", "Dockside", "Dockside", "Harbour Lane", "Anchors", [], ["Toffees"]),
    "FUL": ("TWK", "Thameswick", "Thameswick", "Cottage Lane", "Bargemen", [], ["Cottagers"]),
    "IPS": ("EMR", "Eastmoor Town", "Eastmoor", "Moorside Road", "Ploughmen", [], ["Tractor Boys", "Blues"]),
    "LEI": ("HCR", "Highcross", "Highcross", "Highcross Stadium", "Stags", ["King Power"], ["Foxes"]),
    "LIV": ("NBG", "Northbridge", "Northbridge", "Bridge End", "Herons", [], ["Reds"]),
    "MCI": ("CDV", "Calder Vale", "Calder Vale", "Vale Stadium", "Skylarks", ["Manchester City", "Etihad", "City"], ["Citizens", "Cityzens"]),
    "MUN": ("RDW", "Redwater", "Redwater", "Redwater Park", "Ironmen", ["Manchester United", "Man United"], ["Red Devils"]),
    "NEW": ("HLD", "Halden Town", "Halden", "Halden Park", "Pipers", [], ["Magpies", "Toon"]),
    "NFO": ("GRH", "Greenhurst", "Greenhurst", "Hurst Ground", "Wardens", ["Nottingham Forest", "Nottingham", "Forest", "Nott'm"], ["Tricky Trees"]),
    "SOU": ("PTW", "Portwell", "Portwell", "Portwell Dock", "Mariners", [], ["Saints"]),
    "TOT": ("LLF", "Lilyford", "Lilyford", "Lilyford Lane", "Larks", [], ["Lilywhites"]),
    "WHU": ("IRN", "Ironside", "Ironside", "Ironside Stadium", "Foundrymen", ["West Ham United", "West Ham"], ["Hammers", "Irons"]),
    "WOL": ("KGM", "Kingsmere", "Kingsmere", "Kingsmere Field", "Wolfhounds", [], ["Wanderers"]),
}

# Arabic spellings found in the saved Arabic recaps. A leading و/ف/ب/ل prefix is kept, joined with a tatweel.
ARABIC_CLUBS = {
    "CHE": ["تشيلسي"], "WHU": ["وست هام", "ويست هام"], "BOU": ["بورنموث"], "LEI": ["ليستر"],
    "LIV": ["ليفربول", "الريدز"], "MCI": ["مانشستر سيتي", "سيتي"], "NFO": ["نوتنغهام فورست", "فورست"], "BRE": ["برينتفورد"],
}
ARABIC_PLACES = {"ستامفورد بريدج": "CHE", "ستام": "CHE", "أنفيلد": "LIV", "الفيتاليتي": "BOU"}
ARABIC_PLAYERS = {
    "نيكولاس جاكسون": "Nicolas Jackson", "نيكولاس": "Nicolas Jackson", "جاكسون": "Nicolas Jackson",
    "مويسيس كايسيدو": "Moisés Caicedo", "كايسيدو": "Moisés Caicedo", "مالو غوستو": "Malo Gusto",
    "نوني مادويكي": "Noni Madueke", "مادويكي": "Noni Madueke", "نوني": "Noni Madueke",
    "بيدرو نيتو": "Pedro Neto", "بيدرو": "Pedro Neto", "نيتو": "Pedro Neto",
    "محمد كودوس": "Mohammed Kudus", "كودوس": "Mohammed Kudus", "إنزو فرنانديز": "Enzo Fernández", "إنزو": "Enzo Fernández",
}
ARABIC_TEXT = {"بأسماء فرق حقيقية": "بأسماء فرق خيالية"}  # "with real team names" -> "with fictional team names"
AR_BEFORE = r"(^|[\s،؛(\"«])(وب|ول|فب|لل|و|ف|ب|ل)??"
AR_AFTER = r"(?=$|[\s،؛.,:!?)\"»])"

MANAGERS = {
    "Mikel Arteta": "Ivo Marsh", "Unai Emery": "Joel Hartley", "Andoni Iraola": "Pau Lindell", "Thomas Frank": "Erik Vass",
    "Fabian Hürzeler": "Timo Raskin", "Enzo Maresca": "Aldo Ferrante", "Oliver Glasner": "Rolf Haber", "Sean Dyche": "Glen Marsden",
    "David Moyes": "Iain Corbett", "Marco Silva": "Tiago Leal", "Kieran McKenna": "Ross Kilbride", "Steve Cooper": "Neil Ashdown",
    "Ruud van Nistelrooy": "Daan Verhoef", "Arne Slot": "Joost Brink", "Pep Guardiola": "Jordi Casals", "Ruben Amorim": "Nuno Prates",
    "Erik ten Hag": "Bram Kuiper", "Eddie Howe": "Alan Pryor", "Nuno Espírito Santo": "Rui Abrantes", "Russell Martin": "Craig Lowther",
    "Ivan Juric": "Goran Pavic", "Ange Postecoglou": "Theo Kallis", "Julen Lopetegui": "Iker Zubia", "Graham Potter": "Mark Sefton",
    "Gary O'Neil": "Dean Fallon", "Vítor Pereira": "Hugo Matos",
    "Maresca": "Ferrante", "Nuno": "Abrantes", "Guardiola": "Casals", "Arteta": "Marsh", "Postecoglou": "Kallis", "Iraola": "Lindell",
}
REFEREES = {
    "Michael Oliver": "Martin Ellery", "Anthony Taylor": "Graham Pryce", "Simon Hooper": "Owen Lacey",
    "Chris Kavanagh": "Paul Brannigan", "Jarred Gillett": "Rhys Danton", "Craig Pawson": "Stuart Kemble",
    "Stuart Attwell": "Lee Marwood", "Robert Jones": "Gareth Penrose", "Peter Bankes": "Neil Fairbank",
    "Samuel Barrott": "Adam Cresswell", "Darren England": "Carl Hesketh", "Tony Harrington": "Ian Thewlis",
}
VARIANTS = {"Ruben Dias": "Rúben Dias"}  # spellings models use for squad names

FIRST = ("Tomas", "Kofi", "Luca", "Mateo", "Joel", "Ibrahim", "Rafael", "Noah", "Elias", "Sami", "Theo", "Jonah",
         "Kwame", "Emil", "Aron", "Dario", "Felix", "Hugo", "Ilan", "Jalen", "Leon", "Marek", "Nils", "Oskar", "Pavel",
         "Quentin", "Rico", "Soren", "Tobi", "Ugo", "Viktor", "Wade", "Yusuf", "Zane", "Arlo", "Caleb", "Dmitri", "Femi",
         "Gael", "Hamza", "Idris", "Jonas", "Karim", "Lars", "Milo", "Nico", "Obi", "Pim", "Rui", "Seb", "Tariq", "Uli",
         "Vince", "Wes", "Yann", "Zeki", "Ansel", "Bram", "Cyril", "Dele", "Eero", "Fabio", "Goran", "Hakim", "Isak",
         "Jory", "Kasper", "Lamine", "Mats", "Nuri", "Otto", "Piet", "Ravi", "Silas", "Teodor", "Valentin", "Yaw")
LAST = ("Okafor", "Lindqvist", "Marlowe", "Adeyemi", "Kerrigan", "Valdés", "Thorne", "Mbeki", "Castell", "Oyelaran",
        "Hartigan", "Novak", "Ferreira", "Quist", "Abara", "Delacroix", "Whitlock", "Sørensen", "Pellegrino", "Rowntree",
        "Koenig", "Achterberg", "Strand", "Moreau", "Ekwueme", "Haldane", "Fontaine", "Rask", "Nwosu", "Calloway",
        "Brandt", "Osei", "Lennox", "Kowalczyk", "Ashby", "Duarte", "Hollis", "Ogbu", "Renshaw", "Ilori", "Vance",
        "Sauer", "Morrow", "Takács", "Garnier", "Abiodun", "Bellweather", "Carvalho", "Draxby", "Elstree", "Fairclough",
        "Gutteridge", "Hessler", "Ingram", "Jovanic", "Kallström", "Larrea", "Mabaso", "Nakamura", "Oduya", "Pratt",
        "Quintero", "Rademaker", "Sallis", "Tembo", "Ulloa", "Varga", "Wexford", "Yildiz", "Zubak", "Aldana", "Blackwood",
        "Cosgrove", "Dunmore", "Esposito", "Fennimore", "Grieve", "Hallgren", "Iwuchukwu", "Jessop", "Kinsella",
        "Lombardi", "Mensah", "Nordin", "Oakes", "Pemberton", "Rautio", "Stavros", "Thackeray", "Udeze", "Vukovic",
        "Westergaard", "Yeboah", "Zoller", "Amankwah", "Brennan", "Cardoso", "Delmar", "Forsberg")
STEMS = ("Ash", "Brack", "Cald", "Dun", "Elm", "Fen", "Gar", "Hal", "Kel", "Lang", "Mar", "Nor", "Pen", "Rad", "Stan", "Thorn", "Wex")
ENDINGS = ("ford", "ley", "wick", "by", "more", "ton", "well", "hurst")

WORD = r"(?<![\w])({})(?![\w])"
NAMEISH = re.compile(r"[A-Z\u0600-\u06FF]")


def _hash(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)


def _alternation(pairs: dict[str, str], template: str = WORD) -> re.Pattern | None:
    keys = sorted((k for k in pairs if k), key=len, reverse=True)
    return re.compile(template.format("|".join(map(re.escape, keys)))) if keys else None


class Identity:
    def __init__(self, mode: str | None = None):
        self.mode = (mode or os.environ.get("BTR_NAMES", "fictional")).lower()
        league = json.loads(LEAGUE_FILE.read_text(encoding="utf-8")) if LEAGUE_FILE.exists() else {"clubs": {}}
        self.real_clubs = league["clubs"]
        self.players = {f"{code}-{role}": p["name"] for code, club in self.real_clubs.items() for role, p in club["xi"].items()}
        self.fake_players = self._fake_players()
        self.code_map = {code: c[0] for code, c in CLUBS.items()}
        self._code_re = _alternation(self.code_map, r"\b({})\b")
        self._arabic = self._arabic_pairs()
        self._arabic_re = _alternation(self._arabic, AR_BEFORE + "({})" + AR_AFTER)

    @property
    def fictional(self) -> bool:
        return self.mode == "fictional"

    def _fake_players(self) -> dict[str, str]:
        """Deterministic names; every surname is unique league-wide so surname-only prose stays unambiguous."""
        taken = {tok for name in self.players.values() for tok in re.split(r"[\s\-']+", name)}
        first = [f for f in FIRST if f not in taken]
        last = [s for s in dict.fromkeys(LAST + tuple(p + s for p in STEMS for s in ENDINGS)) if s not in taken]
        out, used = {}, set()
        for pid in sorted(self.players, key=_hash):
            h = _hash(pid)
            surname = next(last[(h + k) % len(last)] for k in range(len(last)) if last[(h + k) % len(last)] not in used)
            used.add(surname)
            out[pid] = f"{first[h % len(first)]} {surname}"
        return out

    def club(self, code: str) -> dict:
        """The fictional club for a real code: what the frontend and overlays show."""
        c = CLUBS[code]
        return {"code": c[0], "name": c[1], "short": c[2], "stadium": c[3], "nickname": c[4]}

    # ---------- replacement tables ----------
    def _global_pairs(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for code, (_, name, short, stadium, *_rest) in CLUBS.items():
            real = self.real_clubs.get(code, {})
            pairs |= {real.get("name", ""): name, real.get("short", ""): short, real.get("stadium", ""): stadium}
        pairs |= {real: self.fake_players[pid] for pid, real in self.players.items()}
        pairs |= {v: self.fake_players[pid] for v, real in VARIANTS.items() for pid, n in self.players.items() if n == real}
        pairs |= MANAGERS | REFEREES | {"Premier League": "Simulated League"}
        pairs.pop("", None)
        return pairs

    @lru_cache(maxsize=64)
    def _table(self, roster_key: tuple) -> tuple[re.Pattern | None, dict[str, str]]:
        """One combined pattern per match: global names plus that match's surnames, first names and club aliases."""
        pairs = self._global_pairs()
        codes = {pid.split("-")[0] for pid in roster_key}
        for code in codes & set(CLUBS):
            _, _, short, stadium, nick, alts, nicks = CLUBS[code]
            pairs |= {a: (stadium if a in ("Etihad", "King Power") else short) for a in alts}
            pairs |= {n: nick for n in nicks}
        surnames, firsts = {}, {}
        for pid in roster_key:
            real, fake = self.players.get(pid, ""), self.fake_players.get(pid, "")
            parts, fparts = real.split(), fake.split()
            if len(parts) > 1 and len(fparts) > 1:
                surnames[" ".join(parts[1:])] = fparts[-1]
                surnames.setdefault(parts[-1], fparts[-1])
                firsts.setdefault(parts[0], []).append(fparts[0])
        pairs |= {k: v for k, v in surnames.items() if k not in pairs}
        pairs |= {f: v[0] for f, v in firsts.items() if len(v) == 1 and f not in surnames and f not in pairs}
        return _alternation(pairs), pairs

    def _arabic_pairs(self) -> dict[str, str]:
        pairs = {f: CLUBS[code][2] for code, forms in ARABIC_CLUBS.items() for f in forms}
        pairs |= {f: CLUBS[code][3] for f, code in ARABIC_PLACES.items()}
        by_name = {name: pid for pid, name in self.players.items()}
        pairs |= {f: self.fake_players[by_name[real]] for f, real in ARABIC_PLAYERS.items() if real in by_name}
        return pairs | ARABIC_TEXT

    # ---------- public API ----------
    def skin(self, obj, roster=None):
        """A copy of any JSON-like value with every real identity replaced. `roster` (the match's real player
        ids) adds surname-only, first-name-only and club-nickname replacements for that match."""
        if not self.fictional:
            return obj
        pattern, pairs = self._table(tuple(sorted(roster or ())))
        memo: dict[str, str] = {}
        return self._walk(obj, pattern, pairs, memo)

    def _walk(self, obj, pattern, pairs, memo):
        if isinstance(obj, str):
            if obj not in memo:
                memo[obj] = self._str(obj, pattern, pairs)
            return memo[obj]
        if isinstance(obj, (list, tuple)):
            return [self._walk(x, pattern, pairs, memo) for x in obj]
        if isinstance(obj, dict):
            return {self._walk(k, pattern, pairs, memo): self._walk(v, pattern, pairs, memo) for k, v in obj.items()}
        return obj

    def _arabic_sub(self, m: re.Match) -> str:
        lead, prefix, word = m.group(1), m.group(2) or "", m.group(3)
        rep = self._arabic[word]
        latin = not re.match(r"[؀-ۿ]", rep)
        return lead + prefix + ("ـ " if prefix and latin else "") + rep

    def _str(self, s: str, pattern, pairs) -> str:
        if len(s) < 3 or not NAMEISH.search(s):  # ids, enums and numbers: nothing to replace
            return s
        if self._arabic_re and re.search(r"[؀-ۿ]", s):
            s = self._arabic_re.sub(self._arabic_sub, s)
        if pattern:
            s = pattern.sub(lambda m: pairs[m.group(1)], s)
        return self._code_re.sub(lambda m: self.code_map[m.group(1)], s) if self._code_re else s

    def unskin_id(self, value: str) -> str:
        """A fictional club code or player id from a request, mapped back to the internal one."""
        if not self.fictional:
            return value
        back = {v: k for k, v in self.code_map.items()}
        return re.sub(r"\b(" + "|".join(back) + r")\b", lambda m: back[m.group(1)], value)

    def unskin_name(self, name: str) -> str:
        if not self.fictional:
            return name
        return {v: self.players[k] for k, v in self.fake_players.items()}.get(name, name)

    def leaks(self, obj, roster=None) -> list[str]:
        """Compliance check: every real identity still present in an output."""
        text = json.dumps(obj, ensure_ascii=False)
        terms = set(self.players.values()) | set(MANAGERS) | set(REFEREES) | {"Premier League"}
        for code, c in self.real_clubs.items():
            terms |= {c["name"], c["short"], c["stadium"]} | set(CLUBS[code][6]) - {"Blues"}
        for pid in roster or ():
            real = self.players.get(pid, "")
            terms |= {real.split()[-1]} if " " in real else set()
            terms |= set(CLUBS.get(pid.split("-")[0], ("",) * 7)[5]) | set(CLUBS.get(pid.split("-")[0], ("",) * 7)[6])
        latin = _alternation(dict.fromkeys(t for t in terms if t))
        arabic = _alternation(dict.fromkeys(a for a in self._arabic if a not in ARABIC_TEXT), AR_BEFORE + "({})" + AR_AFTER)
        hits = {m.group(1) for m in latin.finditer(text)} if latin else set()
        hits |= {m.group(3) for m in arabic.finditer(text)} if arabic else set()
        hits |= {m.group(1) for m in self._code_re.finditer(text)}
        return sorted(hits)


@lru_cache(maxsize=1)
def identity() -> Identity:
    return Identity()
