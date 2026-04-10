"""
teams_notifier.py — Send messages to Microsoft Teams via webhook URL.
Set your webhook URL in the environment:
    $env:TEAMS_WEBHOOK_URL="webhookurl"
"""
import os
import urllib.request
import json

WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

def send(message: str) -> bool:
    """
    Send a plain message to Teams.
    Returns True if successful, False if not.
    """
    if not WEBHOOK_URL:
        return False

    # Teams uses Adaptive Card format for rich messages
    payload = json.dumps({
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type":    "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": message,
                            "wrap": True
                        }
                    ]
                }
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        print(f"  ⚠️  Teams 전송 실패: {e}")
        return False

def notify_question_and_answer(question: str, answer: str, sources: list = None):
    """Send a Q&A pair to Teams."""
    src_text = f"\n📄 출처: {', '.join(sources)}" if sources else ""
    message  = (
        f"🤝 **컨설턴트 에이전트 답변**\n\n"
        f"**Q:** {question}\n\n"
        f"**A:** {answer}"
        f"{src_text}"
    )
    return send(message)
