#!/usr/bin/env python3
"""
Инструмент для Claude - обновление знаний Gemini
Используй когда нужно научить Gemini чему-то новому
"""
import json
from datetime import datetime
from pathlib import Path

KNOWLEDGE_PATH = Path(__file__).parent / "knowledge"
CONTEXT_FILE = KNOWLEDGE_PATH / "system_context.md"
FACTS_FILE = KNOWLEDGE_PATH / "facts.json"

def add_fact(category, fact):
    """Add a new fact to Gemini's knowledge"""
    facts = {}
    if FACTS_FILE.exists():
        facts = json.loads(FACTS_FILE.read_text())
    
    if category not in facts:
        facts[category] = []
    
    facts[category].append({
        "fact": fact,
        "added": datetime.now().isoformat(),
        "by": "Claude"
    })
    
    FACTS_FILE.write_text(json.dumps(facts, indent=2, ensure_ascii=False))
    return f"Added fact to '{category}'"

def list_facts():
    """List all facts"""
    if not FACTS_FILE.exists():
        return "No facts yet"
    
    facts = json.loads(FACTS_FILE.read_text())
    output = []
    for cat, items in facts.items():
        output.append(f"\n=== {cat} ===")
        for item in items:
            output.append(f"  • {item['fact']}")
    return "\n".join(output)

def update_context_section(section_name, content):
    """Update a section in system context"""
    if not CONTEXT_FILE.exists():
        return "Context file not found"
    
    ctx = CONTEXT_FILE.read_text()
    
    # Add/update section at the end
    marker = f"## {section_name}"
    if marker in ctx:
        # Replace section - find next ## or end
        start = ctx.find(marker)
        end = ctx.find("\n## ", start + len(marker))
        if end == -1:
            end = len(ctx)
        ctx = ctx[:start] + f"{marker}\n{content}\n" + ctx[end:]
    else:
        ctx += f"\n\n{marker}\n{content}\n"
    
    CONTEXT_FILE.write_text(ctx)
    return f"Updated section: {section_name}"

def add_instruction(instruction):
    """Add new instruction for Gemini"""
    return add_fact("instructions", instruction)

def get_knowledge_stats():
    """Get stats about Gemini's knowledge"""
    stats = {
        "context_file": CONTEXT_FILE.exists(),
        "context_size": 0,
        "facts_count": 0,
        "categories": []
    }
    
    if CONTEXT_FILE.exists():
        stats["context_size"] = len(CONTEXT_FILE.read_text())
    
    if FACTS_FILE.exists():
        facts = json.loads(FACTS_FILE.read_text())
        stats["categories"] = list(facts.keys())
        stats["facts_count"] = sum(len(v) for v in facts.values())
    
    return stats

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  update_gemini_knowledge.py stats")
        print("  update_gemini_knowledge.py list")
        print("  update_gemini_knowledge.py add <category> <fact>")
        print("  update_gemini_knowledge.py instruct <instruction>")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "stats":
        print(json.dumps(get_knowledge_stats(), indent=2))
    elif cmd == "list":
        print(list_facts())
    elif cmd == "add" and len(sys.argv) >= 4:
        result = add_fact(sys.argv[2], " ".join(sys.argv[3:]))
        print(result)
    elif cmd == "instruct" and len(sys.argv) >= 3:
        result = add_instruction(" ".join(sys.argv[2:]))
        print(result)
    else:
        print("Unknown command")
