#!/usr/bin/env python3
"""
MCP Tools для Claude Mailbox
"""
import sqlite3
import json
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).parent / "mailbox.db"
CONFIG = {
    "bot_token": "7579834718:AAHOxEjB6GvqKFA0ztql2qKvOg0u3LqDU2M",
    "chat_id": "171656163"
}

def mailbox_check():
    """Проверить входящие вопросы"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, content, created_at FROM messages 
                 WHERE direction = 'incoming' AND status = 'pending' 
                 ORDER BY created_at""")
    questions = [{"id": r[0], "content": r[1], "created_at": r[2]} for r in c.fetchall()]
    conn.close()
    return {"pending_questions": len(questions), "questions": questions}

def mailbox_reply(question_id, answer):
    """Ответить на вопрос и отправить в Telegram"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Mark question answered
    c.execute("UPDATE messages SET status = 'answered', answered_at = CURRENT_TIMESTAMP WHERE id = ?", 
              (question_id,))
    
    # Save answer
    c.execute("INSERT INTO messages (direction, content, status) VALUES ('outgoing', ?, 'sent')", 
              (answer,))
    
    conn.commit()
    conn.close()
    
    # Send to Telegram immediately
    url = f"https://api.telegram.org/bot{CONFIG['bot_token']}/sendMessage"
    data = {
        "chat_id": CONFIG["chat_id"],
        "text": f"📤 <b>Ответ на вопрос #{question_id}:</b>\n\n{answer}",
        "parse_mode": "HTML"
    }
    
    try:
        req = urllib.request.Request(url, 
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.load(response)
            return {"success": result.get("ok", False), "question_id": question_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

def mailbox_history(limit=10):
    """История сообщений"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, direction, content, status, created_at 
                 FROM messages ORDER BY created_at DESC LIMIT ?""", (limit,))
    messages = []
    for r in c.fetchall():
        messages.append({
            "id": r[0],
            "direction": "incoming" if r[1] == "incoming" else "outgoing", 
            "content": r[2][:200],
            "status": r[3],
            "created_at": r[4]
        })
    conn.close()
    return {"messages": messages}

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    
    if cmd == "check":
        result = mailbox_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif cmd == "reply" and len(sys.argv) >= 4:
        qid = int(sys.argv[2])
        answer = " ".join(sys.argv[3:])
        result = mailbox_reply(qid, answer)
        print(json.dumps(result, indent=2))
    elif cmd == "history":
        result = mailbox_history()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: mcp_tools.py [check|reply <id> <answer>|history]")
