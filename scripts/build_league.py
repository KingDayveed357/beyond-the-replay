"""Build the Premier League 2024/25 identity pack the engine plays with.

Reads the local datasets (not committed: they were scraped from public sites and are not ours to
redistribute) and writes a compact, derived file: data/league/pl_2024_25.json with clubs, a 4-3-3
starting XI per club, and ability ratings derived from real per-90 stats plus final league position.

Matches built from this pack are simulations: real names, invented events. No crests, badges or
photos are used anywhere.

Usage:  python scripts/build_league.py [--src "<folder with datasets/>"]
"""
import argparse
import csv
import json
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / "Documents" / "premier league data from 2016 to 2025" / "datasets"
OUT = ROOT / "data" / "league" / "pl_2024_25.json"

# Players never shown in simulated matches, with the reason recorded.
EXCLUDED = {"Diogo Jota": "died in July 2025; not depicted in invented events"}

CLUBS = {  # name in data -> (code, short name, stadium, capacity, primary colour, secondary colour)
    "Arsenal": ("ARS", "Arsenal", "Emirates Stadium", 60704, "#DB0007", "#FFFFFF"),
    "Aston Villa": ("AVL", "Aston Villa", "Villa Park", 42682, "#670E36", "#95BFE5"),
    "Bournemouth": ("BOU", "Bournemouth", "Vitality Stadium", 11307, "#DA291C", "#000000"),
    "Brentford": ("BRE", "Brentford", "Gtech Community Stadium", 17250, "#E30613", "#FFFFFF"),
    "Brighton and Hove Albion": ("BHA", "Brighton", "Amex Stadium", 31876, "#0057B8", "#FFFFFF"),
    "Chelsea": ("CHE", "Chelsea", "Stamford Bridge", 40173, "#034694", "#FFFFFF"),
    "Crystal Palace": ("CRY", "Crystal Palace", "Selhurst Park", 25486, "#1B458F", "#C4122E"),
    "Everton": ("EVE", "Everton", "Goodison Park", 39414, "#003399", "#FFFFFF"),
    "Fulham": ("FUL", "Fulham", "Craven Cottage", 29589, "#FFFFFF", "#000000"),
    "Ipswich Town": ("IPS", "Ipswich", "Portman Road", 29673, "#3A64A3", "#FFFFFF"),
    "Leicester City": ("LEI", "Leicester", "King Power Stadium", 32259, "#003090", "#FDBE11"),
    "Liverpool": ("LIV", "Liverpool", "Anfield", 61276, "#C8102E", "#F6EB61"),
    "Manchester City": ("MCI", "Man City", "Etihad Stadium", 53400, "#6CABDD", "#1C2C5B"),
    "Manchester United": ("MUN", "Man Utd", "Old Trafford", 74310, "#DA291C", "#FBE122"),
    "Newcastle United": ("NEW", "Newcastle", "St James' Park", 52305, "#241F20", "#FFFFFF"),
    "Nottingham Forest": ("NFO", "Nott'm Forest", "City Ground", 30404, "#DD0000", "#FFFFFF"),
    "Southampton": ("SOU", "Southampton", "St Mary's Stadium", 32384, "#D71920", "#FFFFFF"),
    "Tottenham Hotspur": ("TOT", "Spurs", "Tottenham Hotspur Stadium", 62850, "#132257", "#FFFFFF"),
    "West Ham United": ("WHU", "West Ham", "London Stadium", 62500, "#7A263A", "#1BB1E7"),
    "Wolverhampton Wanderers": ("WOL", "Wolves", "Molineux", 31750, "#FDB913", "#231F20"),
}


# Typical 2024/25 starting XIs mapped onto the engine's 4-3-3 roles (GK RB CB1 CB2 LB DM CMR CML RW ST LW).
# Every name is checked against the dataset; any miss falls back to the automatic picker and is reported.
LINEUPS = {
    "Arsenal": "David Raya|Jurriën Timber|William Saliba|Gabriel Magalhães|Myles Lewis-Skelly|Thomas Partey|Martin Ødegaard|Declan Rice|Bukayo Saka|Kai Havertz|Gabriel Martinelli",
    "Aston Villa": "Emiliano Martínez|Matty Cash|Ezri Konsa|Pau Torres|Lucas Digne|Boubacar Kamara|John McGinn|Youri Tielemans|Morgan Rogers|Ollie Watkins|Marcus Rashford",
    "Bournemouth": "Kepa|Adam Smith|Illia Zabarnyi|Dean Huijsen|Milos Kerkez|Tyler Adams|Lewis Cook|Ryan Christie|Justin Kluivert|Evanilson|Antoine Semenyo",
    "Brentford": "Mark Flekken|Michael Kayode|Nathan Collins|Ethan Pinnock|Keane Lewis-Potter|Christian Nørgaard|Mikkel Damsgaard|Vitaly Janelt|Bryan Mbeumo|Yoane Wissa|Kevin Schade",
    "Brighton and Hove Albion": "Bart Verbruggen|Joël Veltman|Jan Paul van Hecke|Lewis Dunk|Pervis Estupiñán|Carlos Baleba|Yasin Ayari|João Pedro|Yankuba Minteh|Danny Welbeck|Kaoru Mitoma",
    "Chelsea": "Robert Sánchez|Malo Gusto|Levi Colwill|Trevoh Chalobah|Marc Cucurella|Moisés Caicedo|Enzo Fernández|Cole Palmer|Noni Madueke|Nicolas Jackson|Pedro Neto",
    "Crystal Palace": "Dean Henderson|Daniel Muñoz|Maxence Lacroix|Marc Guéhi|Tyrick Mitchell|Adam Wharton|Jefferson Lerma|Daichi Kamada|Ismaïla Sarr|Jean-Philippe Mateta|Eberechi Eze",
    "Everton": "Jordan Pickford|Jake O'Brien|James Tarkowski|Jarrad Branthwaite|Vitalii Mykolenko|Idrissa Gueye|James Garner|Abdoulaye Doucouré|Iliman Ndiaye|Beto|Dwight McNeil",
    "Fulham": "Bernd Leno|Kenny Tete|Joachim Andersen|Calvin Bassey|Antonee Robinson|Sander Berge|Sasa Lukic|Andreas Pereira|Adama Traoré|Raúl Jiménez|Alex Iwobi",
    "Ipswich Town": "Arijanet Muric|Ben Johnson|Dara O'Shea|Jacob Greaves|Leif Davis|Sam Morsy|Jens Cajuste|Kalvin Phillips|Omari Hutchinson|Liam Delap|Jack Clarke",
    "Leicester City": "Mads Hermansen|James Justin|Wout Faes|Conor Coady|Victor Kristiansen|Wilfred Ndidi|Boubakary Soumaré|Bilal El Khannouss|Jordan Ayew|Jamie Vardy|Stephy Mavididi",
    "Liverpool": "Alisson Becker|Trent Alexander-Arnold|Ibrahima Konaté|Virgil van Dijk|Andy Robertson|Ryan Gravenberch|Dominik Szoboszlai|Alexis Mac Allister|Mohamed Salah|Luis Díaz|Cody Gakpo",
    "Manchester City": "Ederson|Kyle Walker|Rúben Dias|Manuel Akanji|Josko Gvardiol|Mateo Kovacic|Bernardo Silva|Ilkay Gündogan|Savinho|Erling Haaland|Jérémy Doku",
    "Manchester United": "André Onana|Noussair Mazraoui|Matthijs de Ligt|Harry Maguire|Diogo Dalot|Manuel Ugarte|Bruno Fernandes|Kobbie Mainoo|Amad Diallo|Rasmus Højlund|Alejandro Garnacho",
    "Newcastle United": "Nick Pope|Tino Livramento|Fabian Schär|Dan Burn|Lewis Hall|Bruno Guimarães|Sandro Tonali|Joelinton|Jacob Murphy|Alexander Isak|Anthony Gordon",
    "Nottingham Forest": "Matz Sels|Ola Aina|Nikola Milenkovic|Murillo|Neco Williams|Nicolás Domínguez|Morgan Gibbs-White|Elliot Anderson|Anthony Elanga|Chris Wood|Callum Hudson-Odoi",
    "Southampton": "Aaron Ramsdale|Yukinari Sugawara|Taylor Harwood-Bellis|Jan Bednarek|Kyle Walker-Peters|Flynn Downes|Mateus Fernandes|Joe Aribo|Tyler Dibling|Cameron Archer|Adam Armstrong",
    "Tottenham Hotspur": "Guglielmo Vicario|Pedro Porro|Cristian Romero|Micky van de Ven|Destiny Udogie|Yves Bissouma|Pape Sarr|James Maddison|Brennan Johnson|Dominic Solanke|Son Heung-Min",
    "West Ham United": "Alphonse Areola|Aaron Wan-Bissaka|Maximilian Kilman|Konstantinos Mavropanos|Emerson|Edson Álvarez|Tomás Soucek|Lucas Paquetá|Mohammed Kudus|Jarrod Bowen|Crysencio Summerville",
    "Wolverhampton Wanderers": "José Sá|Nélson Semedo|Toti Gomes|Emmanuel Agbadou|Rayan Aït-Nouri|André|João Gomes|Jean-Ricner Bellegarde|Matheus Cunha|Jørgen Strand Larsen|Hwang Hee-Chan",
}
ROLE_ORDER = ["GK", "RB", "CB1", "CB2", "LB", "DM", "CMR", "CML", "RW", "ST", "LW"]


def num(row, key):
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def per90(row, key):
    mins = num(row, "Minutes Played")
    return num(row, key) * 90 / mins if mins else 0.0


def percentile(values, x):
    return sum(v <= x for v in values) / len(values) if values else 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.environ.get("BTR_PL_DATA", str(DEFAULT_SRC)))
    args = ap.parse_args()
    src = Path(args.src)
    info = list(csv.DictReader(open(src / "premier_player_info.csv", encoding="utf-8")))
    stats = {r["player_name"]: r for r in csv.DictReader(open(src / "player_stats_2024_2025_season.csv", encoding="utf-8"))}
    table = list(csv.DictReader(open(src / "league_table/home_and_away/gameweek_2024/2024_gameweek_38.csv", encoding="utf-8")))
    club_stats = {r["club_name"]: r for r in csv.DictReader(open(src / "club_stats/2024_season_club_stats.csv", encoding="utf-8"))}
    table_by = {r["name"]: r for r in table}

    players = []
    for r in info:
        s = stats.get(r["player_name"])
        if not s or r["player_club"] not in CLUBS or r["player_name"] in EXCLUDED:
            continue
        players.append({"name": r["player_name"], "club": r["player_club"], "pos": r["player_position"],
                        "nat": r["player_country"], "foot": s["Preferred Foot"], "s": s,
                        "mins": num(s, "Minutes Played"), "apps": num(s, "Appearances") or num(s, "appearances_")})

    def score(p):  # role-relevant per-90 profile
        s = p["s"]
        if p["pos"] == "Goalkeeper":
            return per90(s, "Saves Made") + 2 * per90(s, "Clean Sheets")
        if p["pos"] == "Defender":
            return per90(s, "Duels Won") + per90(s, "Total Tackles") + per90(s, "Interceptions") + num(s, "pass_accuracy") / 20
        if p["pos"] == "Midfielder":
            return num(s, "pass_accuracy") / 10 + per90(s, "Duels Won") / 2 + 10 * per90(s, "XA") + 5 * per90(s, "XG")
        return 12 * per90(s, "XG") + 8 * per90(s, "XA") + num(s, "dribble_accuracy") / 25

    regulars = [p for p in players if p["mins"] >= 900]
    pools = {pos: [score(p) for p in regulars if p["pos"] == pos] for pos in ("Goalkeeper", "Defender", "Midfielder", "Forward")}
    max_points = max(num(t, "points") for t in table)
    min_points = min(num(t, "points") for t in table)

    clubs_out = {}
    for club, (code, short, stadium, cap, c1, c2) in CLUBS.items():
        squad = sorted([p for p in players if p["club"] == club], key=lambda p: -p["mins"])
        by = lambda pos: [p for p in squad if p["pos"] == pos]
        gk = max(by("Goalkeeper"), key=lambda p: (p["apps"], p["mins"]))
        defs = by("Defender")[:5]
        fb_signal = lambda p: per90(p["s"], "cross_attempts") + per90(p["s"], "dribble_attempts")
        full_backs = sorted(defs, key=fb_signal, reverse=True)[:2]
        centre = [p for p in defs if p not in full_backs][:2]
        left = next((p for p in full_backs if p["foot"] == "Left"), full_backs[-1])
        right = next(p for p in full_backs if p is not left)
        mids = by("Midfielder")[:3]
        dm = max(mids, key=lambda p: per90(p["s"], "Total Tackles") + per90(p["s"], "Interceptions"))
        others = [p for p in mids if p is not dm]
        cml = next((p for p in others if p["foot"] == "Left"), others[-1])
        cmr = next(p for p in others if p is not cml)
        fwds = by("Forward")
        st = max(fwds[:4], key=lambda p: per90(p["s"], "XG") * min(p["mins"], 2000))
        wingers = [p for p in fwds if p is not st][:2]
        while len(wingers) < 2:  # thin forward lines: borrow the most attacking unused midfielder
            spare = [p for p in by("Midfielder") if p not in mids and p not in wingers]
            wingers.append(max(spare, key=lambda p: per90(p["s"], "dribble_attempts")))
        # Many elite wide forwards play on the opposite side to their stronger foot.
        rw = next((p for p in wingers if p["foot"] == "Left"), wingers[0])
        lw = next(p for p in wingers if p is not rw)
        xi = {"GK": gk, "RB": right, "CB1": centre[0], "CB2": centre[1], "LB": left, "DM": dm,
              "CMR": cmr, "CML": cml, "RW": rw, "ST": st, "LW": lw}
        by_name = {p["name"]: p for p in squad}
        wanted = LINEUPS.get(club, "").split("|")
        for role, name in zip(ROLE_ORDER, wanted):
            if name in by_name:
                xi[role] = by_name[name]
            else:
                print(f"  ! {club}: '{name}' not in dataset; {role} keeps {xi[role]['name']}")
        names = [p["name"] for p in xi.values()]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            print(f"  ! {club}: duplicate players {dupes}")

        t = table_by[club]
        club_pct = (num(t, "points") - min_points) / (max_points - min_points)
        ratings = {}
        for role, p in xi.items():
            player_pct = percentile(pools[p["pos"]], score(p))
            ratings[role] = round(0.45 + 0.20 * (0.55 * player_pct + 0.45 * club_pct), 3)
        cs = club_stats.get(club, {})
        gp = num(cs, "Games Played") or 38
        clubs_out[code] = {
            "name": club, "short": short, "stadium": stadium, "capacity": cap, "colours": [c1, c2],
            "season_2024_25": {"position": int(t["position"]), "points": int(num(t, "points")), "won": int(num(t, "games_won")),
                               "drawn": int(num(t, "games_drawn")), "lost": int(num(t, "games_lost")),
                               "goals_for": int(num(t, "goals_for")), "goals_against": int(num(t, "goals_against")),
                               "xg_per_match": round(num(cs, "XG") / gp, 2)},
            "xi": {role: {"name": p["name"], "nationality": p["nat"], "foot": p["foot"], "rating": ratings[role],
                          "season": {"apps": int(p["apps"]), "minutes": int(p["mins"]), "goals": int(num(p["s"], "Goals")),
                                     "assists": int(num(p["s"], "Assists")), "xg": round(num(p["s"], "XG"), 2),
                                     "pass_accuracy": int(num(p["s"], "pass_accuracy"))}}
                   for role, p in xi.items()},
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"season": "2024/25", "competition": "Premier League", "formation": "4-3-3",
                               "excluded": EXCLUDED, "clubs": clubs_out,
                               "note": "Real clubs and players, simulated matches. Ratings derived from 2024/25 per-90 stats and final position."},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    for code, c in clubs_out.items():
        print(code, c["season_2024_25"]["position"], " | ".join(f"{r}:{p['name']}({p['rating']})" for r, p in c["xi"].items()))


if __name__ == "__main__":
    main()
