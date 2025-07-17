import os
import chromadb
from sentence_transformers import SentenceTransformer

# 🔧 Setup
chroma_client = chromadb.Client()
collection = chromadb.PersistentClient(path="db").get_or_create_collection("sf6")

model = SentenceTransformer("all-MiniLM-L6-v2")  # klein, snel, goed genoeg

# 📁 Lees alle .txt-bestanden in de map
data_folder = "../data/sf6/txt"  # verander dit naar jouw map
for filename in os.listdir(data_folder):
    if filename.endswith(".txt"):
        with open(os.path.join(data_folder, filename), "r", encoding="utf-8") as f:
            text = f.read()

        # Maak een vector
        embedding = model.encode(text).tolist()

        # Voeg toe aan de vectorstore
        collection.add(
            documents=[text],
            embeddings=[embedding],
            ids=[filename]  # uniek id
        )

print("✅ Alles is opgeslagen in ChromaDB!")
