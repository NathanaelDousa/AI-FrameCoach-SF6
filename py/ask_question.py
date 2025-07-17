from sentence_transformers import SentenceTransformer
import chromadb

# Setup
client = chromadb.PersistentClient(path="db")
collection = client.get_collection("sf6")
model = SentenceTransformer("all-MiniLM-L6-v2")

# 🔍 Vraag
question = input("Vraag over SF6: ")
question_vector = model.encode(question).tolist()

# 🔎 Zoek
results = collection.query(
    query_embeddings=[question_vector],
    n_results=3
)

print("\n🔁 Meest relevante stukken info:\n")
for i, doc in enumerate(results["documents"][0]):
    print(f"[{i+1}] {doc}\n")
