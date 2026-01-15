#!/usr/bin/env python3
"""
Claude Mailbox Bot v3.0 - Gemini с полным контекстом системы
Иерархия: User → Claude (главный) → Gemini (исполнитель)
"""
import json
import urllib.request
import sqlite3
import time
import subprocess
from pathlib import Path

DB_PATH = Path(__file__).parent / "mailbox.db"
KNOWLEDGE_PATH = Path(__file__).parent / "knowledge"
AGI_DB_PATH = Path("/home/ubuntu/agi-news-agent/knowledge/news.db")

CONFIG = {
    "bot_token": "7579834718:AAHOxEjB6GvqKFA0ztql2qKvOg0u3LqDU2M",
    "chat_id": "171656163"
}

def load_facts():
    """Load additional facts"""
    facts_file = KNOWLEDGE_PATH / "facts.json"
    if facts_file.exists():
        import json as j
        facts = j.loads(facts_file.read_text())
        output = ["\n## ДОПОЛНИТЕЛЬНЫЕ ФАКТЫ"]
        for cat, items in facts.items():
            output.append(f"\n### {cat}:")
            for item in items:
                output.append(f"- {item['fact']}")
        return "\n".join(output)
    return ""

def load_system_context():
    """Load full system context for Gemini"""
    context_file = KNOWLEDGE_PATH / "system_context.md"
    if context_file.exists():
        return context_file.read_text()
    return ""

def get_dynamic_context():
    """Get current state of the system"""
    context_parts = []
    
    # AGI Agent stats
    try:
        conn = sqlite3.connect(AGI_DB_PATH)
        c = conn.cursor()
        
        # Rising stars
        c.execute("""SELECT repo_name, stars, stars_per_day, category 
                     FROM github_watchlist WHERE is_rising_star=1 
                     ORDER BY stars_per_day DESC LIMIT 3""")
        rising = c.fetchall()
        if rising:
            context_parts.append("🚀 Текущие Rising Stars:")
            for r in rising:
                context_parts.append(f"  - {r[0]}: {r[1]}⭐ ({r[2]:.0f}/день) [{r[3]}]")
        
        # Stats
        c.execute("SELECT COUNT(*) FROM github_watchlist")
        repos = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM news")
        news = c.fetchone()[0]
        context_parts.append(f"\n📊 В базе: {repos} репозиториев, {news} новостей")
        
        conn.close()
    except Exception as e:
        context_parts.append(f"(AGI DB недоступна: {e})")
    
    # Pending questions for Claude
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM messages WHERE direction='incoming' AND status='pending'")
        pending = c.fetchone()[0]
        if pending > 0:
            context_parts.append(f"\n📬 Вопросов ожидают Claude: {pending}")
        conn.close()
    except:
        pass
    
    return "\n".join(context_parts)

def build_prompt(user_message):
    """Build full prompt with system context"""
    system_context = load_system_context()
    dynamic_context = get_dynamic_context()
    
    prompt = f"""# СИСТЕМНЫЙ КОНТЕКСТ
{system_context}

# ТЕКУЩЕЕ СОСТОЯНИЕ СИСТЕМЫ
{dynamic_context}

# ИНСТРУКЦИИ
- Отвечай развёрнуто и информативно на русском
- Если вопрос сложный или требует действий на сервере - скажи что передашь Claude
- Используй данные из контекста когда релевантно
- Будь полезным помощником

# ВОПРОС ПОЛЬЗОВАТЕЛЯ
{user_message}

# ТВОЙ ОТВЕТ (подробно, на русском):"""
    
    return prompt

def get_gemini_key():
    result = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-d", "-pbkdf2",
         "-in", "/home/ubuntu/.secrets/gemini_api.enc",
         "-pass", "pass:v360admin"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def ask_gemini(question):
    """Ask Gemini with full context"""
    api_key = get_gemini_key()
    prompt = build_prompt(question)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4000
        }
    }
    
    try:
        req = urllib.request.Request(url, 
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.load(response)
        
        if "candidates" in result:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        return None
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def send_message(text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{CONFIG['bot_token']}/sendMessage"
    # Escape HTML special chars if not using HTML
    data = {"chat_id": CONFIG["chat_id"], "text": text[:4000]}
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        req = urllib.request.Request(url, 
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    except Exception as e:
        print(f"Send error: {e}")
        # Try without parse_mode
        try:
            data.pop("parse_mode", None)
            req = urllib.request.Request(url,
                data=json.dumps(data).encode('utf-8'),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except:
            return None

def send_typing():
    url = f"https://api.telegram.org/bot{CONFIG['bot_token']}/sendChatAction"
    data = {"chat_id": CONFIG["chat_id"], "action": "typing"}
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except: pass

def get_updates(offset=0):
    url = f"https://api.telegram.org/bot{CONFIG['bot_token']}/getUpdates?offset={offset}&timeout=30"
    try:
        with urllib.request.urlopen(url, timeout=35) as response:
            return json.load(response)
    except:
        return {"ok": False, "result": []}

def save_message(direction, content, status="pending"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (direction, content, status) VALUES (?, ?, ?)",
              (direction, content, status))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def should_forward_to_claude(text):
    """Determine if question needs Claude"""
    complex_kw = [
        "создай", "сделай", "напиши код", "разверни", "установи", "deploy",
        "настрой", "исправь", "удали", "измени конфиг", "vm", "сервер",
        "mcp hub", "архитектур", "план", "стратег", "claude", "антропик",
        "добавь сервис", "systemd", "nginx", "база данных"
    ]
    return any(kw in text.lower() for kw in complex_kw)

def process_command(text):
    if text == "/start":
        return """🤖 <b>Claude Mailbox v3.0</b>

Привет! Я Gemini - AI помощник в системе.

<b>Иерархия:</b>
👤 Ты (владелец)
🧠 Claude (главный архитектор)
🤖 Я (помощник)

<b>Что я умею:</b>
• Отвечать на вопросы мгновенно
• Показывать AI новости и тренды
• Передавать сложные задачи Claude

<b>Команды:</b>
/status - статус системы
/rising - топ AI проекты
/context - мой контекст
/help - помощь"""

    elif text == "/status":
        ctx = get_dynamic_context()
        return f"📊 <b>Статус системы:</b>\n\n{ctx}"
    
    elif text == "/rising":
        try:
            conn = sqlite3.connect(AGI_DB_PATH)
            c = conn.cursor()
            c.execute("""SELECT repo_name, url, stars, stars_per_day 
                         FROM github_watchlist WHERE is_rising_star=1 
                         ORDER BY stars_per_day DESC LIMIT 5""")
            rising = c.fetchall()
            conn.close()
            
            if rising:
                msg = "🚀 <b>Rising Stars:</b>\n\n"
                for r in rising:
                    msg += f"• <a href='{r[1]}'>{r[0]}</a>\n"
                    msg += f"  ⭐ {r[2]} ({r[3]:.0f}/день)\n\n"
                return msg
            return "Нет данных о rising stars"
        except Exception as e:
            return f"Ошибка: {e}"
    
    elif text == "/context":
        return """🧠 <b>Мой контекст:</b>

Я знаю о:
• Инфраструктуре (VM1, VM2)
• AGI News Agent и его данных
• MCP Hub и инструментах
• Своей роли помощника Claude

Контекст обновляется Claude при сессиях."""

    elif text == "/help":
        return """📖 <b>Помощь:</b>

• Просто пиши вопрос - отвечу
• Начни с "Claude:" для передачи Claude
• Сложные задачи автоматически уходят Claude

<b>Команды:</b>
/status - статус
/rising - AI проекты
/context - мой контекст"""
    
    return None

def run_bot():
    print("🤖 Claude Mailbox Bot v3.0 started")
    send_message("🤖 <b>Gemini Agent v3.0 запущен!</b>\n\nТеперь я знаю контекст всей системы и работаю под руководством Claude.", "HTML")
    
    offset = 0
    
    while True:
        try:
            updates = get_updates(offset)
            
            if updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    
                    if chat_id != CONFIG["chat_id"] or not text:
                        continue
                    
                    # Commands
                    cmd_response = process_command(text)
                    if cmd_response:
                        send_message(cmd_response, "HTML")
                        continue
                    
                    # Forward to Claude?
                    if should_forward_to_claude(text):
                        msg_id = save_message("incoming", text, "pending")
                        send_message(f"📬 Это задача для Claude!\n\nВопрос #{msg_id} сохранён. Claude ответит при следующей сессии.", None)
                        continue
                    
                    # Gemini response
                    send_typing()
                    response = ask_gemini(text)
                    
                    if response:
                        save_message("incoming", text, "answered")
                        save_message("outgoing", response, "sent")
                        send_message(f"🤖 {response}", None)
                    else:
                        msg_id = save_message("incoming", text, "pending")
                        send_message(f"⚠️ Временная ошибка. Вопрос #{msg_id} передан Claude.", None)
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nBot stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_bot()

# NOTE: facts.json is loaded via build_prompt() which reads system_context.md
# To add facts awareness, update load_system_context() in next version

def get_recent_changes():
    """Get recent changes from auto-deployer"""
    import sqlite3
    changes_db = Path("/home/ubuntu/auto-deployer/changes.db")
    if not changes_db.exists():
        return []
    try:
        conn = sqlite3.connect(changes_db)
        c = conn.cursor()
        c.execute("""SELECT project, filepath, change_type, committed, created_at 
                     FROM changes ORDER BY created_at DESC LIMIT 10""")
        changes = [{"project": r[0], "file": r[1], "type": r[2], 
                    "committed": "✅" if r[3] else "⏳", "time": r[4][:16]} 
                   for r in c.fetchall()]
        conn.close()
        return changes
    except:
        return []
