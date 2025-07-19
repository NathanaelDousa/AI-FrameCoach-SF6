# AI FrameCoach SF6

**FrameCoach SF6** is an AI-powered coaching assistant for **Street Fighter 6**. It uses semantic search and a local large language model (LLM) to provide accurate, competitive-level answers about moves, frame data, strategies, and character-specific tools.

---

##  Features

-  Searchable database of frame data and character guides
-  AI-generated answers via a local LLM (Gemma)
-  Example questions you can ask:
  - "What are Zangief’s best anti-airs?"
  - "How plus is JP’s OD Amnesia on hit?"
  - "What is the startup on Cammy’s crouching heavy punch?"

---

##  Tech Stack

- [Sentence Transformers](https://www.sbert.net/) for semantic vector embeddings
- [ChromaDB](https://www.trychroma.com/) as a vector database
- [Flask](https://flask.palletsprojects.com/) for the backend API
- [Ollama](https://ollama.com/) to run local LLMs (e.g., `mistral`, `gemma`)
- JSON and TXT files with move data and guides (converted and ingested)

---

##  AI Prompt Design

The LLM is instructed to behave like a **world-class Street Fighter 6 coach**, with a focus on:
- Competitive insights
- Accurate use of frame data
- Concise and helpful explanations
- No fluff, no speculation

---

## Requirements
Make sure your system has the following installed:

Python 3.10 or higher

pip (Python package installer)

Ollama (for running local LLMs)

---

##  Setup Instructions

1. **Install Ollama**  
   https://ollama.com/download  
   Once installed, pull the model you want to use (e.g., gemma or mistral):
   ```
   ollama pull gemma:2b
   or 
   ollama pull mistral

   You can test if it's working with:
   ollama run gemma:2b

2. **Clone the Project & Set Up Python**  
   git clone https://github.com/NathanaelDousa/AI-FrameCoach-SF6
   cd AI-FrameCoach-SF6

   (Optional) Create a virtual environment:
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. **Install Dependencies**  
   pip install flask flask-cors sentence-transformers chromadb requests

4. **Prepare the Database (Ingest Data)**
   First, make sure your move and guide files are stored as plain .txt files (one file per character or topic) inside the data/ folder.
   Then run:
   python ingest_texts.py

   This script will:
   - Load all .txt files in the data/ folder
   - Convert them into vector embeddings
   - Store them in a local ChromaDB database

5. **Run the Server**  
   Start your Flask app:
   python app.py

   You should see something like:
    * Running on http://127.0.0.1:5000
   Open your browser and go to:
   http://localhost:5000

6. **Ask Questions**  
   You can now ask questions like:

   - What are Zangief’s best anti-airs?
   - How plus is Cammy’s crouching light punch?
   - Tell me how to use Manon’s command grab
   The app will:

   Embed your question
   Retrieve the top relevant documents using ChromaDB
   Feed both the context and your question into the local LLM (Gemma or Mistral)
   Return a clean and accurate response    

**Notes**
   You can change the model name in app.py:
   ```
   MODEL = "gemma"  # or "mistral", etc.
   ```
   Make sure Ollama is running while using the app.

   If you add or update files in data/, run ingest_texts.py again.


