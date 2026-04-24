import os
import json
import requests
import resend
from google import genai
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")       # shared: GEMINI_API_KEY
load_dotenv(Path(__file__).parent / ".env", override=True)  # local: project-specific overrides

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
FROM_EMAIL = os.environ.get("FROM_EMAIL", "Tech Digest <onboarding@resend.dev>")

client = genai.Client(api_key=GEMINI_API_KEY)


def load_subscribers() -> list[str]:
    with open("subscribers.txt") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


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
                "comments": item["comment_count"],
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


def fetch_github_trending(limit=25):
    repos = []
    try:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://api.github.com/search/repositories?q=created:>{since}&sort=stars&order=desc&per_page={limit}"
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "TechDigest/1.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        for repo in r.json().get("items", []):
            repos.append({
                "name": repo["full_name"],
                "description": repo.get("description", "") or "",
                "stars": repo["stargazers_count"],
                "language": repo.get("language", "") or "",
                "topics": repo.get("topics", []),
                "url": repo["html_url"],
            })
    except Exception as e:
        print(f"GitHub Trending error: {e}")
    return repos


def curate_with_gemini(posts: list) -> dict:
    posts_text = json.dumps(posts, ensure_ascii=False)
    week = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""Você é um curador de conteúdo tech. Abaixo estão posts populares da semana de Hacker News, Lobste.rs e dev.to.

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

    response = client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def curate_github_with_gemini(repos: list) -> list:
    repos_text = json.dumps(repos, ensure_ascii=False)

    prompt = f"""Você é um curador de projetos open source. Abaixo estão repositórios do GitHub que explodiram em estrelas esta semana.

Selecione os 6 mais interessantes e relevantes para desenvolvedores. Priorize projetos com propósito claro, inovadores ou que resolvam problemas reais.

Retorne APENAS um JSON com esta estrutura, sem markdown, sem explicações:
[
  {{
    "name": "owner/repo",
    "description": "1 frase clara sobre o que faz",
    "why": "1-2 frases sobre por que está a ganhar tração esta semana",
    "language": "linguagem principal",
    "stars": número de estrelas,
    "url": "url do repositório"
  }}
]

Repositórios:
{repos_text}
"""

    response = client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
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

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#2b7489",
    "JavaScript": "#f1e05a",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C": "#555555",
    "Shell": "#89e051",
}


def build_html(digest: dict, github_repos: list) -> str:
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

    github_html = ""
    for repo in github_repos:
        lang = repo.get("language", "")
        lang_color = LANGUAGE_COLORS.get(lang, "#6b7280")
        stars = repo.get("stars", 0)
        github_html += f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin-bottom:14px;background:#fff;">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
            <h3 style="margin:0;font-size:15px;font-weight:600;">
              <a href="{repo["url"]}" style="color:#1f2937;text-decoration:none;">&#128196; {repo["name"]}</a>
            </h3>
            <div style="display:flex;gap:8px;align-items:center;">
              {f'<span style="background:{lang_color}22;color:{lang_color};font-size:11px;padding:2px 8px;border-radius:12px;font-weight:600;">{lang}</span>' if lang else ""}
              <span style="color:#6b7280;font-size:12px;">&#11088; {stars:,}</span>
            </div>
          </div>
          <p style="color:#374151;font-size:14px;margin:8px 0 4px;line-height:1.5;">{repo["description"]}</p>
          <p style="color:#6b7280;font-size:13px;margin:0;line-height:1.5;">{repo["why"]}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;background:#fff;">
  <div style="background:linear-gradient(135deg,#1f2937 0%,#111827 100%);padding:40px 32px;text-align:center;">
    <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Tech Digest</h1>
    <p style="color:#9ca3af;margin:8px 0 0;font-size:14px;">Semana de {week} &middot; HN &middot; Lobste.rs &middot; dev.to &middot; GitHub</p>
  </div>
  <div style="padding:32px;background:#fff;">
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin-bottom:32px;">
      <p style="margin:0;color:#1d4ed8;font-size:15px;line-height:1.6;"><strong>Esta semana:</strong> {digest["summary"]}</p>
    </div>

    {posts_html}

    <h2 style="font-size:18px;font-weight:700;color:#1f2937;margin:32px 0 16px;padding-top:24px;border-top:2px solid #e5e7eb;">
      &#128640; GitHub em Destaque
    </h2>
    <p style="color:#6b7280;font-size:13px;margin:-8px 0 16px;">Repositórios que explodiram em estrelas esta semana</p>
    {github_html}
  </div>
  <div style="background:#f3f4f6;padding:24px 32px;text-align:center;border-top:1px solid #e5e7eb;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">Gerado automaticamente com Gemini AI &middot; HN, Lobste.rs, dev.to, GitHub</p>
  </div>
</body></html>"""


def main():
    print("Fetching posts...")
    lobsters = fetch_lobsters()
    hn = fetch_hackernews()
    devto = fetch_devto()
    github = fetch_github_trending()
    all_posts = lobsters + hn + devto
    print(f"Posts: {len(all_posts)} (Lobste.rs={len(lobsters)}, HN={len(hn)}, dev.to={len(devto)})")
    print(f"GitHub repos: {len(github)}")

    print("Curating posts with Gemini...")
    digest = curate_with_gemini(all_posts)
    print(f"Selected {len(digest['posts'])} posts")

    print("Curating GitHub repos with Gemini...")
    github_curated = curate_github_with_gemini(github)
    print(f"Selected {len(github_curated)} repos")

    html = build_html(digest, github_curated)

    resend.api_key = RESEND_API_KEY
    subscribers = load_subscribers()
    result = resend.Emails.send({
        "from": FROM_EMAIL,
        "to": subscribers,
        "subject": digest["digest_title"],
        "html": html,
    })
    print(f"Email sent to {len(subscribers)} subscriber(s)! ID: {result['id']}")


if __name__ == "__main__":
    main()
