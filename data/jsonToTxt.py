import json

# Laad de JSON data in vanuit een bestand
with open('data/sf6/characters_stats.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

lines = []

# Loop door elk karakter en maak een nette zin
for character, stats in data.items():
    line = (
        f"{character} heeft een loopsnelheid van {stats['Walk Speed']}, "
        f"een dash snelheid van {stats['Dash Speed']}, "
        f"een dash afstand van {stats['Dash Distance']}, "
        f"{stats['Health']} HP en een prejump van {stats['Prejump']} frames."
    )
    lines.append(line)

# Schrijf alles naar een tekstbestand
with open('data/sf6/character_facts.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(lines))

print("✅ character_facts.txt is succesvol aangemaakt!")
