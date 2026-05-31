# parserTG — buhFOP Content Pipeline

Automated news pipeline for [@aifopukr](https://t.me/aifopukr) — content about FOP, PKU, NBU for Ukrainian entrepreneurs.

## Architecture

```
Sources
├── Telethon (MTProto) → @nbu_ua, @tax_gov_ua, @Minfin_com_ua, @bu911
└── CloakBrowser → buhgalter911.com (via @bu911 links, auto-enriches full article text)
        ↓
   Pub/Sub (tg-raw-ingested)
        ↓
   Processor (Cloud Run Service)
   - Creates INGESTED drafts in Firestore
   - Notifies Approver (no GPT)
        ↓
   Approver (Cloud Run Service) — Telegram bot
   - Ingest thread: [TG] [Social] [Both] [SKIP]
   - TG → GPT expert post → review thread → [📢 TG] [🔄 RED] [Skip]
   - Social → GPT provocative post → review thread → [🐦 Twitter] [🧵 Threads]
   - Both → generates both versions
        ↓
   Posting:
   - TG channel @aifopukr
   - Twitter (Tweepy, free tier)
   - Threads (Meta API)
        ↓
   Firestore posts/ — knowledge base for future agents
```

## Tech Stack

| Layer | Tool |
|-------|------|
| Ingest | Telethon (MTProto), CloakBrowser (Playwright stealth) |
| Queue | Google Pub/Sub |
| Storage | Firestore (Native, `nam5`) |
| AI | OpenRouter (`deepseek/deepseek-chat:free`) or OpenAI fallback |
| Posting | python-telegram-bot, Tweepy, Threads API |
| Infra | Cloud Run Jobs + Services, Cloud Scheduler |
| Secrets | Google Secret Manager |

## Infrastructure

| Service | Type | Trigger | Instances |
|---------|------|---------|-----------|
| ingest | Job | Cloud Scheduler (every 15min) | 0 |
| processor | Service | Pub/Sub push | 0–2 |
| approver | Service | Telegram webhook | 0–2 |

## GCP Setup

- Region: `europe-west1`
- Project: `optimum-tea-481710-u3`
- SA: `tg-parser-runner@optimum-tea-481710-u3.iam.gserviceaccount.com` (runtime + deploy)
- Firestore: `(default)` database in `nam5` (Native mode)

Enable APIs once (manual):
- Cloud Run, Artifact Registry, Firestore, Secret Manager, Cloud Scheduler, Pub/Sub, IAM Credentials

## Secrets (Secret Manager)

```
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELETHON_STRING_SESSION
OPENROUTER_API_KEY
TG_BOT_TOKEN
BUHGALTER911_LOGIN
BUHGALTER911_PASSWORD
TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_SECRET
THREADS_APP_ID
THREADS_APP_SECRET
THREADS_ACCESS_TOKEN
THREADS_USER_ID
```

## GitHub Variables

```bash
WORKSPACE_ID=fop_ukr
INGEST_LIMIT=50
BOOTSTRAP_MAX_AGE_DAYS=        # leave empty
PUBSUB_VERIFICATION_AUDIENCE=  # leave empty
APPROVER_NOTIFY_URL=           # set after first deploy
```

## LLM Backend

Set `OPENROUTER_API_KEY` for OpenRouter (free DeepSeek) or `OPENAI_API_KEY` for OpenAI.
If both are set, OpenRouter takes priority.

## GPT Profiles

| Profile | Use | Tone |
|---------|-----|------|
| `default` | TG channel posts | Expert, analytical, references PKU/NBU |
| `social` | Twitter/Threads | Provocative, drives engagement, no hashtags |

## Web Enricher (CloakBrowser)

When `@bu911` posts a teaser with a `buhgalter911.com` URL, the ingest job automatically:
1. Launches CloakBrowser (stealth Chromium)
2. Navigates to the article URL
3. Logs in if needed (`BUHGALTER911_LOGIN/PASSWORD`)
4. Replaces TG teaser text with the full article text

Falls back silently to original TG text if enrichment fails.

## Firestore Schema

```
workspaces/{WORKSPACE_ID}
  sources/{source_id}
    type, tg_entity, enabled, last_message_id, last_message_date, bootstrapped

  drafts/{draft_id}
    source_id, source_type, origin_chat, origin_text
    tg_text, social_text, post_targets (tg|social|both)
    status: INGESTED → RED_READY → POSTED | SKIPPED
    ingest_message_id, review_message_id
    tg_posted, twitter_posted, threads_posted
    posted_at

  posts/{draft_id}          ← knowledge base for future agents
    tg_text, social_text, origin_text, source_id, source_type, posted_at
```

## First-time Bootstrap

```bash
# 1. Seed workspace + sources
python -m scripts.init_firestore

# 2. Deploy via GitHub Actions (workflow_dispatch)

# 3. Set Telegram webhook
TG_BOT_TOKEN=... WEBHOOK_URL=https://APPROVER_URL/telegram/webhook \
  python tools/set_webhook.py

# 4. Bootstrap ingest (sets last_message_id to current, publishes nothing)
gcloud run jobs execute ingest --region europe-west1 --wait
# Verify: second run should fetch 0 new messages
gcloud run jobs execute ingest --region europe-west1 --wait
```

## Re-bootstrap sources (if spam from old messages)

```bash
# Reset all sources to bootstrap from current latest
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json \
python3 -c "
from google.cloud import firestore
db = firestore.Client(project='optimum-tea-481710-u3')
for doc in db.collection('workspaces/fop_ukr/sources').stream():
    if doc.to_dict().get('enabled', True):
        doc.reference.update({'bootstrapped': False, 'last_message_id': 0})
        print('reset:', doc.id)
"
gcloud run jobs execute ingest --region europe-west1 --wait
```

## CI/CD

GitHub Actions (`workflow_dispatch` only).

Required secrets: `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_SERVICE_ACCOUNT`
Required variables: `WORKSPACE_ID`, `INGEST_LIMIT`

## Tests

```bash
pip install -r requirements-test.txt
pytest tests/ -v
```

93 tests covering: ingest utils, processor utils, approver utils, web enricher, GPT profiles, processor endpoint, approver endpoint.
