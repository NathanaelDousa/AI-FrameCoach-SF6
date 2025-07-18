import os
import json

input_folder = "sf6"
output_folder = "../py/output_txt"

os.makedirs(output_folder, exist_ok=True)

def move_to_text(character, move):
    lines = [
        f"Character: {character}",
        f"Move: {move.get('move', 'Unknown')}",
        f"Startup: {move.get('startup', 'Unknown')}",
        f"Active Frames: {move.get('activeframes', 'Unknown')}",
        f"Recovery: {move.get('recovery', 'Unknown')}",
        f"On Hit: {move.get('onhit', 'Unknown')}",
        f"On Block: {move.get('onblock', 'Unknown')}",
        f"Cancelable: {move.get('cancellable', 'Unknown')}",
        f"Notes: {move.get('notes', '')}",
    ]
    return "\n".join(lines)


for filename in os.listdir(input_folder):
    if filename.endswith(".json"):
        filepath = os.path.join(input_folder, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        character = data.get("character", filename.replace(".json", ""))
        output_lines = []

        for move in data.get("moves", []):
            text_block = move_to_text(character, move)
            output_lines.append(text_block)


        output_path = os.path.join(output_folder, f"{character}.txt")
        with open(output_path, "w", encoding="utf-8") as f_out:
            f_out.write("\n\n".join(output_lines))

print("✅ Alle JSON-bestanden zijn geconverteerd naar .txt-bestanden.")
