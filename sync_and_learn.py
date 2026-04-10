"""
server.py — FastAPI HTTP server for the consultant agent.

Receives questions via HTTP POST and returns answers.
Used with Power Automate to connect Microsoft Teams to the agent.

Run:
    python server.py

Test:
    curl -X POST http://localhost:8000/ask \
      -H "Content-Type: application/json" \
      -d '{"question": "What is our VPN policy?"}'
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional

from knowledge_base import search, get_stats
from teams_notifier import notify_question_and_answer, WEBHOOK_URL
import anthropic

# ── Setup ──────────────────────────────────────────────────────────────────────
app    = FastAPI(title="Consultant Agent API", version="1.0")
client = anthropic.Anthropic()

MODEL = "claude-sonnet-4-20250514"

# Simple API key to protect the endpoint
# Set this in your environment: $env:AGENT_API_KEY="your-secret-key"
AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "shinwootns-agent-key")

SYSTEM_PROMPT = """
You are a helpful Consultant Agent for Shinwootns, a small cloud security company based in South Korea.

You answer questions strictly based on the company documents provided to you.
These documents represent the official knowledge base of the organization.

Rules:
- Only answer based on the document context provided to you
- Always cite which document your answer came from using [Source: filename]
- If the answer is not in the provided documents, say:
  "I couldn't find this information in the company documents.
   Please check with the relevant department directly."
- Never make up or infer information not explicitly in the documents
- Be concise, professional, and helpful
- If asked about something sensitive (salary, personal data), decline politely
"""

# ── Request / Response models ──────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    user:     Optional[str] = "Teams User"  # who asked (from Power Automate)

class AskResponse(BaseModel):
    answer:   str
    sources:  list[str]
    question: str
    user:     str

class HealthResponse(BaseModel):
    status:       str
    total_chunks: int
    teams_connected: bool

# ── Auth dependency ────────────────────────────────────────────────────────────
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != AGENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health():
    """Check if the agent is running and knowledge base is loaded."""
    stats = get_stats()
    return {
        "status":          "ok",
        "total_chunks":    stats["total_chunks"],
        "teams_connected": bool(WEBHOOK_URL)
    }


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """
    Receive a question, search the knowledge base, return an answer.
    Power Automate calls this endpoint when a message is sent in Teams.
    """
    question = body.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if len(question) > 2000:
        raise HTTPException(status_code=400, detail="Question too long (max 2000 chars)")

    # Search knowledge base
    chunks  = search(question, n_results=5)
    sources = list(set(c["source"] for c in chunks)) if chunks else []

    # Build context
    if chunks:
        context = "Relevant information retrieved from company documents:\n\n"
        for i, c in enumerate(chunks, 1):
            context += f"[{i}] Source: {c['source']}\n{c['content']}\n\n"
    else:
        context = "No relevant documents found in the knowledge base."

    user_message = f"""Question: {question}

---
{context}
---

Please answer the question based only on the document context above.
Cite your sources."""

    # Ask Claude
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    answer = response.content[0].text

    # Post answer back to Teams
    if WEBHOOK_URL:
        src_text = f"\n📄 출처: {', '.join(sources)}" if sources else ""
        notify_question_and_answer(
            question=f"[{body.user}] {question}",
            answer=answer,
            sources=sources
        )

    return {
        "answer":   answer,
        "sources":  sources,
        "question": question,
        "user":     body.user
    }


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    stats = get_stats()
    print("=" * 55)
    print("🤝  Consultant Agent — HTTP Server")
    print("=" * 55)
    print(f"📚 Knowledge base : {stats['total_chunks']} chunks")
    print(f"📨 Teams webhook  : {'연결됨 ✅' if WEBHOOK_URL else '미설정 ⚠️'}")
    print(f"🔑 API Key        : {AGENT_API_KEY[:8]}...")
    print(f"\n🌐 Server running at: http://localhost:8000")
    print(f"📖 API docs at      : http://localhost:8000/docs")
    print(f"\nPower Automate에서 아래 URL로 POST 요청을 보내세요:")
    print(f"  http://YOUR_IP:8000/ask")
    print(f"  Header: x-api-key: {AGENT_API_KEY}")
    print(f"  Body:   {{\"question\": \"...\", \"user\": \"...\"}}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
