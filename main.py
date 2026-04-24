import os
import json
import requests
import resend
from google import genai
from datetime import datetime

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
TO_EMAIL = os.environ["TO_EMAIL"]
FROM_EMAIL = os.environ.get("FROM_EMAIL", "Tech Digest <onboarding@resend.dev>")

client = genai.Client(api_key=GEMINI_API_KEY)


def fetch_lobsters(limit=20):
    posts = []
    try:
        r = requests.get("https://lobste.rs/hottest.json", timeout=10)
        r.raise_for_status()
        for item in r.json()[:limit]:
            posts.append({
                "title": item["title"],
                "url": item["url"],
                "score": item["score"],
                "comments": item["comments_count"],
                "source": "Lobste.rs",
            })
    except Exception as e:
        print(f"Lobste.rs error: {e}")
    return posts


def fetch_hackernews(limit=30):
    posts = []
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:limit]
        for story_id in ids:
            try:
                story = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5
                ).json()
                if story and story.get("type") == "story" and story.get("url"):
                    posts.append({
                        "title": story.get("title", ""),
                        "url": story["url"],
                        "score": story.get("score", 0),
                        "comments": story.get("descendants", 0),
                        "source": "Hacker News",
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"HackerNews error: {e}")
    return posts


def fetch_devto(limit=20):
    posts = []
    try:
        r = requests.get(f"https://dev.to/api/articles?top=7&per_page={limit}", timeout=10)
        r.raise_for_status()
        for a in r.json():
            posts.append({
                "title": a["title"],
                "url": a["url"],
                "score": a["public_reactions_count"],
                "comments": a["comments_count"],
                "source": "dev.to",
            })
    except Exception as e:
        print(f"dev.to error: {e}")
    return posts


def curate_with_gemini(posts: list) -> dict:
    posts_text = json.dumps(posts, ensure_ascii=False)
    week = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""Você é um curador de conteúdo tech. Abaixo estão posts populares da semana de Reddit, Hacker News e dev.to.

Selecione os 12 mais interessantes e relevantes para desenvolvedores de software (priorize novidades, ferramentas, IA/ML, cloud, DevOps, linguagens).

Para cada post, retorne um JSON com esta estrutura exata:
{{
  "digest_title": "Tech Digest — Semana de {week}",
  "summary": "2 linhas sobre os temas mais quentes dessa semana",
  "posts": [
    {{
      "title": "título claro e direto",
      "summary": "2-3 linhas explicando o que é e por que importa",
      "url": "url original",
      "source": "fonte",
      "category": "AI/ML | Frontend | Backend | DevOps | Tools | Discussion | Security"
    }}
  ]
}}

Retorne APENAS o JSON, sem markdown, sem explicações.

Posts:
{posts_text}
"""

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


CATEGORY_COLORS = {
    "AI/ML": "#6366f1",
    "Frontend": "#f59e0b",
    "Backend": "#10b981",
    "DevOps": "#3b82f6",
    "Tools": "#8b5cf6",
    "Discussion": "#ef4444",
    "Security": "#dc2626",
}


def build_html(digest: dict) -> str:
    week = datetime.now().strftime("%d/%m/%Y")
    posts_html = ""

    for post in digest["posts"]:
        color = CATEGORY_COLORS.get(post["category"], "#6b7280")
        posts_html += f"""
        <div style="border-left:4px solid {color};padding:12px 16px;margin-bottom:20px;background:#f9fafb;border-radius:0 8px 8px 0;">
          <span style="background:{color};color:white;font-size:11px;padding:2px 8px;border-radius:12px;text-transform:uppercase;font-weight:600;">{post["category"]}</span>
          <span style="color:#6b7280;font-size:12px;margin-left:8px;">{post["source"]}</span>
          <h3 style="margin:8px 0;font-size:16px;">
            <a href="{post["url"]}" style="color:#1f2937;text-decoration:none;">{post["title"]}</a>
          </h3>
          <p style="color:#4b5563;font-size:14px;margin:0;line-height:1.6;">{post["summary"]}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;background:#fff;">
  <div style="background:linear-gradient(135deg,#1f2937 0%,#111827 100%);padding:40px 32px;text-align:center;">
    <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Tech Digest</h1>
    <p style="color:#9ca3af;margin:8px 0 0;font-size:14px;">Semana de {week} &middot; Reddit &middot; Hacker News &middot; dev.to</p>
  </div>
  <div style="padding:32px;background:#fff;">
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin-bottom:32px;">
      <p style="margin:0;color:#1d4ed8;font-size:15px;line-height:1.6;"><strong>Esta semana:</strong> {digest["summary"]}</p>
    </div>
    {posts_html}
  </div>
  <div style="background:#f3f4f6;padding:24px 32px;text-align:center;border-top:1px solid #e5e7eb;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">Gerado automaticamente com Gemini AI &middot; Reddit, Hacker News, dev.to</p>
  </div>
</body></html>"""


def main():
    print("Fetching posts...")
    lobsters = fetch_lobsters()
    hn = fetch_hackernews()
    devto = fetch_devto()
    all_posts = lobsters + hn + devto
    print(f"Total: {len(all_posts)} posts (Lobste.rs={len(lobsters)}, HN={len(hn)}, dev.to={len(devto)})")

    print("Curating with Gemini...")
    digest = curate_with_gemini(all_posts)
    print(f"Selected {len(digest['posts'])} posts")

    html = build_html(digest)

    resend.api_key = RESEND_API_KEY
    result = resend.Emails.send({
        "from": FROM_EMAIL,
        "to": [TO_EMAIL],
        "subject": digest["digest_title"],
        "html": html,
    })
    print(f"Email sent! ID: {result['id']}")


if __name__ == "__main__":
    main()
