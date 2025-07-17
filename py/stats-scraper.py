import requests
from bs4 import BeautifulSoup
import json
import os

def scrape_stats():
    url = "https://ultimateframedata.com/sf6/stats"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Fout bij ophalen stats pagina: {r.status_code}")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    container = soup.find(id="contentcontainer")
    if not container:
        print("❌ Contentcontainer niet gevonden op stats pagina!")
        return

    stats_container = container.find(class_="statspagecontainer")
    if not stats_container:
        print("❌ Statspagecontainer niet gevonden!")
        return

    all_stats = {}

    stat_ids = ["walkspeed", "dashspeed", "dashdistance", "health", "prejump"]

    for stat_id in stat_ids:
        stat_div = stats_container.find(id=stat_id)
        if not stat_div:
            print(f"⚠️ Geen statstablecontainer met id '{stat_id}' gevonden, skippen.")
            continue

        table = stat_div.find("table", class_="statstable")
        if not table:
            print(f"⚠️ Geen tabel gevonden in '{stat_id}' div, skippen.")
            continue

        tbody = table.find("tbody")
        if not tbody:
            print(f"⚠️ Geen tbody gevonden in '{stat_id}' tabel, skippen.")
            continue

        rows = tbody.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            char_name = cols[0].get_text(strip=True)
            stat_value = cols[1].get_text(strip=True)

            if char_name not in all_stats:
                all_stats[char_name] = {}

            # Maak stat_id leesbaarder: bv "walkspeed" -> "Walk Speed"
            pretty_stat_name = stat_id.replace("prejumpframes", "Pre-Jump Frames").replace("walkspeed", "Walk Speed").replace("dashspeed", "Dash Speed").replace("dashdistance", "Dash Distance").replace("health", "Health").title()

            all_stats[char_name][pretty_stat_name] = stat_value

    # Save to JSON
    os.makedirs("data/sf6", exist_ok=True)
    with open("data/sf6/characters_stats.json", "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    print(f"✅ Stats per character opgeslagen in data/sf6/characters_stats.json")

if __name__ == "__main__":
    scrape_stats()
