import os
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"  # Gebruik hier het herschrijfmodel

def rewrite_text(text):
    prompt = f"""
You are rewriting a transcript from a video guide about a fighting game character.

Your task is to rewrite the text to make it objective, concise, and professional. Remove any personal phrases such as "I think", "in my opinion", or "I like to", and instead present the information as direct facts or general best practices.

Avoid fluff or unnecessary commentary. Just focus on the essential gameplay mechanics, setups, strategies, or move properties described.

Respond only with the improved version of the text.

---
{text.strip()}
    """

    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })

    if response.status_code == 200:
        return response.json().get("response", "").strip()
    else:
        print("⚠️ Fout bij herschrijven:", response.text)
        return None

def process_folder(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for filename in os.listdir(input_folder):
        if filename.endswith(".txt"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            with open(input_path, "r", encoding="utf-8") as f:
                original_text = f.read()

            print(f"✍️  Herschrijven: {filename}")
            rewritten = rewrite_text(original_text)

            if rewritten:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(rewritten)
                print(f"✅ Opgeslagen: {output_path}")
            else:
                print(f"❌ Geen output voor: {filename}")

if __name__ == "__main__":
    input_folder = "input"
    output_folder = "output_txt"
    process_folder(input_folder, output_folder)
