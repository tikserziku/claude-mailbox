#!/usr/bin/env python3
"""
Claude Mailbox - Асинхронное общение с Claude через Telegram
Пользователь оставляет вопросы, Claude отвечает когда есть сессия
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "mailbox.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        direction TEXT,
        content TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        answered_at TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def add_question(content):
    """Добавить вопрос от пользователя"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (direction, content, status) VALUES ('incoming', ?, 'pending')", (content,))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def add_answer(question_id, content):
    """Добавить ответ от Claude"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Mark question as answered
    c.execute("UPDATE messages SET status = 'answered', answered_at = CURRENT_TIMESTAMP WHERE id = ?", (question_id,))
    # Add answer
    c.execute("INSERT INTO messages (direction, content, status) VALUES ('outgoing', ?, 'pending')", (content,))
    answer_id = c.lastrowid
    conn.commit()
    conn.close()
    return answer_id

def get_pending_questions():
    """Получить неотвеченные вопросы"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content, created_at FROM messages WHERE direction = 'incoming' AND status = 'pending' ORDER BY created_at")
    results = c.fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1], "created_at": r[2]} for r in results]

def get_pending_answers():
    """Получить неотправленные ответы"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content FROM messages WHERE direction = 'outgoing' AND status = 'pending'")
    results = c.fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1]} for r in results]

def mark_sent(msg_id):
    """Отметить ответ как отправленный"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE messages SET status = 'sent' WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

def get_history(limit=20):
    """История сообщений"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, direction, content, status, created_at FROM messages ORDER BY created_at DESC LIMIT ?", (limit,))
    results = c.fetchall()
    conn.close()
    return results

if __name__ == "__main__":
    import sys
    init_db()
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "init":
        print("Database initialized")
    elif cmd == "pending":
        questions = get_pending_questions()
        if questions:
            print(f"📬 {len(questions)} pending questions:")
            for q in questions:
                print(f"\n[{q['id']}] {q['created_at']}")
                print(f"   {q['content'][:200]}...")
        else:
            print("📭 No pending questions")
    elif cmd == "history":
        for msg in get_history():
            direction = "📥" if msg[1] == "incoming" else "📤"
            print(f"{direction} [{msg[0]}] {msg[3]}: {msg[2][:50]}...")
    elif cmd == "add" and len(sys.argv) > 2:
        content = " ".join(sys.argv[2:])
        msg_id = add_question(content)
        print(f"Question added: #{msg_id}")
