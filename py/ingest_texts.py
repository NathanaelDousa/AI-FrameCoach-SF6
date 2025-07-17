import os
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="db")

# Verwijder en herbouw de collectie (alle bestaande data wissen)
if "sf6" in [c.name for c in client.list_collections()]:
    client.delete_collection("sf6")

collection = client.create_collection("sf6")

def build_description(move_dict):
    return (
        f"{move_dict.get('Move', 'Onbekende move')} heeft {move_dict.get('Startup', 'onbekend')} startup frames, "
        f"{move_dict.get('Active Frames', 'onbekend')} active frames en {move_dict.get('Recovery', 'onbekend')} recovery frames. "
        f"On hit: {move_dict.get('On Hit', 'onbekend')}, on block: {move_dict.get('On Block', 'onbekend')}. "
        f"Cancelable: {move_dict.get('Cancelable', 'geen')}. "
        f"Notes: {move_dict.get('Notes', 'geen')}"
    )

def parse_file(file_path):
    with open(file_path, encoding="utf-8") as f:
        content = f.read().strip().split("\n\n")  # Splits op lege regels = per move

    documents = []
    for block in content:
        lines = block.strip().splitlines()
        move_data = {}
        for line in lines:
            if ": " in line:
                key, val = line.split(": ", 1)
                move_data[key.strip()] = val.strip()
        if move_data:
            documents.append(build_description(move_data))
    return documents

# Inladen en opslaan
docs = []
ids = []

txt_folder = "output_txt"  # pas aan als je folder anders heet
counter = 0

for file in os.listdir(txt_folder):
    if file.endswith(".txt"):
        full_path = os.path.join(txt_folder, file)
        move_descriptions = parse_file(full_path)

        for desc in move_descriptions:
            docs.append(desc)
            ids.append(f"doc-{counter}")
            counter += 1

# Indexeren
embeddings = model.encode(docs).tolist()
collection.add(documents=docs, embeddings=embeddings, ids=ids)

print(f" {len(docs)} moves geïndexeerd in vector DB.")
