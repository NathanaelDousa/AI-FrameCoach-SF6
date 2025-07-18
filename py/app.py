from sentence_transformers import SentenceTransformer
import chromadb
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

CHARACTERS = [
    "Ryu", "Ken", "Chun-Li", "Guile", "Juri", "Luke", "Jamie", "Kimberly", "JP",
    "Lily", "Manon", "Marisa", "Zangief", "Blanka", "Cammy", "Dhalsim", "E. Honda",
    "Dee Jay", "A.K.I.", "Rashid", "Ed", "Akuma"
]

def extract_character_from_question(question):
    lower_q = question.lower()
    for char in CHARACTERS:
        if char.lower() in lower_q:
            return char
    return ""  # fallback als geen naam wordt gevonden

app = Flask(__name__)
CORS(app) 
# Setup
model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="db")
collection = client.get_collection("sf6")
# Debug: Toon alle documenten waarin "Zangief" voorkomt
for result in collection.get()["documents"]:
    if "Zangief" in result:
        print("✅ Zangief gevonden in DB:")
        print(result)


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3"  # of "mistral" of wat je gebruikt

@app.route("/")
def index():
    return render_template("index.html")
    
@app.route("/ask", methods=["POST"])
def ask():
    print("Ask route triggered")
    data = request.json
    print("Ontvangen vraag:", data) 
    question = data.get("question", "")

    question_vector = model.encode(question).tolist()
    results = collection.query(query_embeddings=[question_vector], n_results=10)

    # Filter op basis van karakternaam in de documenten
    character_name = extract_character_from_question(question)  # Bijvoorbeeld 'Blanka'
    relevant_docs = [doc for doc in results["documents"][0] if character_name.lower() in doc.lower()]
    context = "\n\n".join(relevant_docs[:3])  # max 3 relevante documenten


    prompt = f"""You are a world-class Street Fighter 6 coach who explains setups, frame data, and strategy clearly and concisely. Your answers are direct, accurate, and tailored to competitive players. Avoid speculative language and do not use phrases like 'in my opinion.'

    Use the context below to answer the question. Focus on clarity and usefulness.

    Context:
    {context}

    Question: {question}
    Answer:"""

    # Vraag het aan Ollama
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })

    result = response.json()
    answer = result.get("response", "Er ging iets mis met de AI.")

    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True)