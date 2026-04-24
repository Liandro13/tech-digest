# Tech Digest

Weekly email newsletter with the most popular tech posts and discussions, curated automatically with Gemini AI.

## Sources

- **Hacker News** — top stories of the week
- **Lobste.rs** — curated tech links
- **dev.to** — top articles from the developer community

## How it works

1. Fetches the top posts from all sources
2. Gemini 2.5 Pro selects and summarises the 12 most relevant for software developers
3. Sends a formatted HTML email to all subscribers every Monday at 8h UTC

## Stack

- **Gemini 2.5 Pro** — curation and summarisation
- **Resend** — email delivery
- **GitHub Actions** — weekly scheduler

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Liandro13/tech-digest.git
cd tech-digest
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
RESEND_API_KEY=your_resend_api_key
FROM_EMAIL=Tech Digest <digest@yourdomain.com>
```

Get your keys at [aistudio.google.com](https://aistudio.google.com/apikey) and [resend.com](https://resend.com).

### 3. Add subscribers

Edit `subscribers.txt` — one email per line:

```
you@example.com
friend@example.com
```

### 4. Run

```bash
python main.py
```

## GitHub Actions

Add these secrets to your repository (`Settings → Secrets → Actions`):

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `RESEND_API_KEY` | Resend API key |
| `FROM_EMAIL` | Sender address using a verified Resend domain |

The workflow runs automatically every Monday at 8h UTC. You can also trigger it manually via `Actions → Weekly Tech Digest → Run workflow`.
