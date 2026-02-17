import os
import requests
from flask import Flask, render_template, request, jsonify
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            pytanie TEXT,
            odpowiedz TEXT,
            typ VARCHAR(10) DEFAULT 'like',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

app = Flask(__name__)

API_URL = "https://router.huggingface.co/together/v1/chat/completions"
HF_TOKEN = os.environ.get("HF_TOKEN")
TXT_FILE = "pamiec.txt"


def get_feedback_examples():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT pytanie, odpowiedz FROM feedback WHERE typ = 'like' ORDER BY created_at DESC LIMIT 10")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return ""
        examples = "\n".join([f"Pytanie: {r[0]}\nDobra odpowiedź: {r[1]}" for r in rows])
        return f"\nPrzykłady dobrych odpowiedzi (ucz się z nich stylu):\n{examples}"
    except:
        return ""


def generate_ai_answer(user_question):
    try:
        with open(TXT_FILE, "r", encoding="utf-8") as f:
            context = f.read()
    except:
        context = "Adrian to Junior Python Developer."

    feedback_section = get_feedback_examples()

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "messages": [
            {
                "role": "system",
                "content": f"""Jesteś AI wersją Adriana - odpowiadasz w jego imieniu.

Fakty o Adrianie (JEDYNE prawdziwe informacje):
{context}
{feedback_section}

ZASADY - przestrzegaj bezwzględnie:
- Odpowiadaj TYLKO na podstawie faktów powyżej, nic nie dodawaj od siebie
- Jeśli czegoś nie ma w faktach - nie wspominaj o tym
- Nigdy nie wspominaj o matematyce ani fizyce
- Odpowiadaj w pierwszej osobie po polsku
- Maksymalnie 3 zdania, nie urywaj w połowie
- Nie zaczynaj od "Myślę że" - mów konkretnie
- Odpowiadaj WYŁĄCZNIE po polsku, nie używaj żadnych innych języków ani alfabetów
- Jeśli pytanie nie dotyczy Adriana, odpowiedz: 'Jestem asystentem AI Adriana i mogę odpowiadać tylko na pytania dotyczące jego doświadczenia i umiejętności.'"""            },
            {
                "role": "user",
                "content": user_question
            }
        ],
        "max_tokens": 400,
        "temperature": 0.3
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            return f"Błąd API {response.status_code}: {response.text}"

        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"Błąd techniczny: {str(e)}"


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    pytanie = data.get("pytanie", "")
    odpowiedz = data.get("odpowiedz", "")
    typ = data.get("typ", "like")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO feedback (pytanie, odpowiedz, typ) VALUES (%s, %s, %s)", (pytanie, odpowiedz, typ))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get("msg", "")
    ai_msg = generate_ai_answer(user_msg)
    return jsonify({"response": ai_msg, "pytanie": user_msg})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))