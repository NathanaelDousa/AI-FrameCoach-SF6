import json
import os

INPUT_DIR = '../data/sf6'
OUTPUT_DIR = 'output_txt'

# Zorg dat output map bestaat
os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename in os.listdir(INPUT_DIR):
    if not filename.endswith('.json'):
        continue
    
    filepath = os.path.join(INPUT_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    character = data.get('character', 'Unknown')
    moves = data.get('moves', [])
    
    lines = [f"Character: {character}\n"]
    
    for move in moves:
        lines.append(f"Move: {move.get('move', 'N/A')}")
        lines.append(f"Startup: {move.get('startup', 'N/A')}")
        lines.append(f"Active Frames: {move.get('activeframes', 'N/A')}")
        lines.append(f"Recovery: {move.get('recovery', 'N/A')}")
        lines.append(f"On Hit: {move.get('onhit', 'N/A')}")
        lines.append(f"On Block: {move.get('onblock', 'N/A')}")
        lines.append(f"Cancelable: {move.get('cancellable', 'N/A')}")
        notes = move.get('notes', '').strip()
        if notes and notes != "--":
            lines.append(f"Notes: {notes}")
        lines.append("")  # lege regel tussen moves
    
    output_filename = f"{character.replace(' ', '_').replace('.', '')}.txt"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Verwerkt: {filename} → {output_filename}")

print("Klaar!")
