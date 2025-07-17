import requests
from sentence_transformers import SentenceTransformer
import chromadb

# Setup
client = chromadb.PersistentClient(path="db")
collection = client.get_collection("sf6")
model = SentenceTransformer("all-MiniLM-L6-v2")

# Vraag
question = input("Vraag over SF6: ")
question_vector = model.encode(question).tolist()

# Context ophalen
results = collection.query(
    query_embeddings=[question_vector],
    n_results=3
)
top_contexts = results["documents"][0]
context_text = "\n\n".join(top_contexts)

# Prompt
prompt = f"""Gebruik onderstaande data uit Street Fighter 6 om een vraag te beantwoorden:

{context_text}

Vraag: {question}
Antwoord:"""

# Vraag sturen naar Ollama
try:
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "gemma",  # of llama3 of mistral
        "prompt": prompt,
        "stream": False
    })

    data = response.json()

    if "response" in data:
        print("\n🤖 AI Antwoord:\n")
        print(data["response"])
    else:
        print("\n⚠️ Er is geen geldig antwoord ontvangen van Ollama.")
        print("Inhoud van response:")
        print(data)

except Exception as e:
    print(f"\n❌ Fout bij versturen naar Ollama: {e}")
