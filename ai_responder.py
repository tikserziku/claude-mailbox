#!/usr/bin/env python3
"""
AI Auto-Responder для Claude Mailbox
Использует Gemini для мгновенных ответов
"""
import json
import urllib.request
import subprocess
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "mailbox.db"

# System prompt для Gemini - пусть ведёт себя как помощник
SYSTEM_PROMPT = """Ты - умный AI помощник. Отвечай кратко и по делу на русском языке.
У тебя есть доступ к системе мониторинга AI новостей (AGI News Agent).
Если вопрос сложный или требует действий на сервере - скажи что передашь вопрос Claude.
Будь дружелюбным и полезным."""

def get_gemini_key():
    """Get decrypted Gemini API key"""
    result = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-d", "-pbkdf2", 
         "-in", "/home/ubuntu/.secrets/gemini_api.enc", 
         "-pass", "pass:v360admin"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def ask_gemini(question, context=""):
    """Ask Gemini and get response"""
    api_key = get_gemini_key()
    
    prompt = f"{SYSTEM_PROMPT}\n\n"
    if context:
        prompt += f"Контекст: {context}\n\n"
    prompt += f"Вопрос: {question}"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }
    
    try:
        req = urllib.request.Request(url,
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"})
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
            
        if "candidates" in result:
            return {
                "success": True,
                "response": result["candidates"][0]["content"]["parts"][0]["text"]
            }
        else:
            error = result.get("error", {}).get("message", "Unknown error")
            return {"success": False, "error": error}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_conversation(question, answer, ai_used="gemini"):
    """Save Q&A to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Save question
    c.execute("INSERT INTO messages (direction, content, status) VALUES ('incoming', ?, 'answered')", 
              (question,))
    q_id = c.lastrowid
    
    # Save answer
    c.execute("INSERT INTO messages (direction, content, status) VALUES ('outgoing', ?, 'sent')",
              (f"[{ai_used}] {answer}",))
    
    conn.commit()
    conn.close()
    return q_id

def should_forward_to_claude(question):
    """Determine if question should wait for Claude session"""
    # Keywords that indicate complex tasks
    complex_keywords = [
        "создай", "сделай", "напиши код", "разверни", "установи",
        "vm", "сервер", "deploy", "настрой", "исправь", "баг",
        "mcp", "архитектур", "план", "стратег"
    ]
    
    q_lower = question.lower()
    return any(kw in q_lower for kw in complex_keywords)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        
        # Check if should forward to Claude
        if should_forward_to_claude(question):
            print(json.dumps({
                "forward_to_claude": True,
                "reason": "Complex task detected"
            }, ensure_ascii=False))
        else:
            result = ask_gemini(question)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Test
        result = ask_gemini("Привет! Как дела?")
        print(json.dumps(result, ensure_ascii=False, indent=2))
