import os
import requests
from bs4 import BeautifulSoup

def scrape_character(char_name):
    url = f"https://ultimateframedata.com/sf6/{char_name}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    # Titel uit <h1> halen
    title = soup.find("h1").get_text(strip=True)

    md_lines = [f"# {title} – Frame Data\n"]

    # Elke sectie (normals, specials, etc.) ophalen via <h2>/<h3> en tabellen
    for heading in soup.select("h2, h3"):
        md_lines.append(f"\n## {heading.get_text(strip=True)}\n")
        # Gefilterde tabelrijen (enkel tekst)
        table = heading.find_next("table")
        if not table:
            continue
        headers = [th.get_text(strip=True) for th in table.select("thead th")]
        rows = table.select("tbody tr")
        for row in rows:
            cells = [td.get_text(" ", strip=True) for td in row.select("td")]
            # Markdown-tabel
            line = "| " + " | ".join(cells) + " |"
            md_lines.append(line)
        md_lines.append("")

    # Opslaan
    os.makedirs("data/sf6", exist_ok=True)
    with open(f"data/sf6/{char_name}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"✅ {char_name}.md gegenereerd!")

for ch in ["akuma", "blanka", "ken", "cammy", "chunli", "deejay", "dhalsim", "ed", "ehonda", "elena", "guile", "jamie", "juri", "kimberly", "lily", "luke", "mbison", "mai", "manon", "marisa", "rashid", "terry", "zangief"]:
    scrape_character(ch)
  # Vervang met andere karakternaam