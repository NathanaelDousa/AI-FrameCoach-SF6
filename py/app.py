from sentence_transformers import SentenceTransformer
import chromadb
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS


app = Flask(__name__)
CORS(app) 
# Setup
model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="db")
collection = client.get_collection("sf6")

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
    results = collection.query(query_embeddings=[question_vector], n_results=3)

    context = "\n\n".join(results["documents"][0])

    prompt = f"""Beantwoord de volgende vraag over Street Fighter 6 op basis van de context.
    
Context:
{context}

Vraag: {question}
Antwoord:"""

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