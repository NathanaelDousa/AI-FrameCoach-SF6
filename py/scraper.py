import os
import requests
from bs4 import BeautifulSoup
import json

def scrape_character(char_name):
    url = f"https://ultimateframedata.com/sf6/{char_name}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Fout bij ophalen pagina {char_name}: status code {r.status_code}")
        return

    soup = BeautifulSoup(r.text, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else char_name

    moves_data = []

    content_div = soup.find(id="contentcontainer")
    if not content_div:
        print(f" Contentcontainer niet gevonden voor {char_name}!")
        return

    moves_divs = content_div.find_all("div", class_="moves")
    if not moves_divs:
        print(f" Geen moves gevonden voor {char_name}!")
        return

    for moves_div in moves_divs:
        movecontainers = moves_div.find_all("div", class_="movecontainer")
        for mc in movecontainers:
            move = {
                "move": mc.find("div", class_="movename").get_text(strip=True) if mc.find("div", class_="movename") else "",
                "startup": mc.find("div", class_="startup").get_text(strip=True) if mc.find("div", class_="startup") else "",
                "totalframes": mc.find("div", class_="totalframes").get_text(strip=True) if mc.find("div", class_="totalframes") else "",
                "basedamage": mc.find("div", class_="basedamage").get_text(strip=True) if mc.find("div", class_="basedamage") else "",
                "attacktype": mc.find("div", class_="attacktype").get_text(strip=True) if mc.find("div", class_="attacktype") else "",
                "cancellable": mc.find("div", class_="cancellable").get_text(strip=True) if mc.find("div", class_="cancellable") else "",
                "notes": mc.find("div", class_="notes").get_text(strip=True) if mc.find("div", class_="notes") else "",
                "whichhitbox": mc.find("div", class_="whichhitbox").get_text(strip=True) if mc.find("div", class_="whichhitbox") else "",
                "onhit": mc.find("div", class_="onhit").get_text(strip=True) if mc.find("div", class_="onhit") else "",
                "onblock": mc.find("div", class_="onblock").get_text(strip=True) if mc.find("div", class_="onblock") else "",
                "activeframes": mc.find("div", class_="activeframes").get_text(strip=True) if mc.find("div", class_="activeframes") else "",
                "recovery": mc.find("div", class_="recovery").get_text(strip=True) if mc.find("div", class_="recovery") else "",
            }
            moves_data.append(move)

    os.makedirs("data/sf6", exist_ok=True)

    with open(f"data/sf6/{char_name}.json", "w", encoding="utf-8") as f:
        json.dump({
            "character": title,
            "moves": moves_data
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ {char_name}.json gegenereerd met {len(moves_data)} moves!")

if __name__ == "__main__":
    characters = [
        "manon",
        "aki",
        "ed",
        "chunli",
        "ehonda",
        "elena",
        "jamie",
        "jp",
        "ken",
        "lily",
        "mai",
        "rashid",
        "terry"
    ]
    for character in characters:
        scrape_character(character)
