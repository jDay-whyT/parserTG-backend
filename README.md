# parserTG — buhFOP Content Pipeline

Automated news pipeline for [@aifopukr](https://t.me/aifopukr) — content about FOP, PKU, NBU for Ukrainian entrepreneurs.

## Architecture

```
Sources
├── Telethon (MTProto) → @nbu_ua, @tax_gov_ua, @verkhovnaradaukrainy, @Minfin_com_ua, @bu911
└── CloakBrowser → buhgalter911.com (via @bu911 links, auto-enriches full article text)
        ↓
   Pub/Sub (tg-raw-ingested)
        ↓
   Processor (Cloud Run Service)
   - Creates INGESTED drafts in Firestore
   - Notifies Approver
        ↓
   Approver (Cloud Run Service) — Telegram bot
   - Ingest thread: [TG] [Social] [Both] [SKIP]
   - TG → GPT expert post → review thread → [POST] [RED] [SKIP]
   - Social → GPT provocative post → review thread → [POST] [RED] [SKIP]
   - Both → generates both versions
        ↓
   Posting:
   - TG channel @aifopukr
   - Twitter (Tweepy, free tier)
   - Threads (planned)
        ↓
   Firestore posts/ — knowledge base for future agents
```

## Tech Stack

| Layer | Tool |
|-------|------|
| Ingest | Telethon (MTProto), CloakBrowser (Playwright stealth) |
| Queue | Google Pub/Sub |
| Storage | Firestore (Native, `nam5`) |
| AI | OpenRouter (DeepSeek V3 / Gemini Flash free) or OpenAI |
| Posting | python-telegram-bot, Tweepy |
| Infra | Cloud Run Jobs + Services, Cloud Scheduler |
| Secrets | Google Secret Manager |

## Infrastructure

| Service | Type | Trigger | Min instances |
|---------|------|---------|---------------|
| ingest | Job | Cloud Scheduler (every 3h) | 0 |
| processor | Service | Pub/Sub push | 0 |
| approver | Service | Telegram webhook | 0 |

## GCP Setup

- Region: `us-central1`
- Firestore: `(default)` database in `nam5` (Native mode)

Enable APIs once (manual):
- Cloud Run, Artifact Registry, Firestore, Secret Manager, Cloud Scheduler, Pub/Sub, IAM Credentials

## Secrets (Secret Manager)

```
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELETHON_STRING_SESSION
OPENROUTER_API_KEY          # or OPENAI_API_KEY
TG_BOT_TOKEN
BUHGALTER911_LOGIN
BUHGALTER911_PASSWORD
TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_SECRET
```

## Environment Variables

```bash
WORKSPACE_ID=fop
GROUP_CHAT_ID=-1003277785413
INGEST_THREAD_ID=357
REVIEW_THREAD_ID=358
PUBLISH_CHANNEL_ID=@aifopukr
GPT_PROFILE=default
SOURCE_CHATS=@nbu_ua,@tax_gov_ua,@verkhovnaradaukrainy,@Minfin_com_ua,@bu911
PUBSUB_TOPIC=tg-raw-ingested
PUBSUB_VERIFICATION_AUDIENCE=https://PROCESSOR_URL
APPROVER_NOTIFY_URL=https://APPROVER_URL/internal/notify
INGEST_LIMIT=50
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324:free
```

For local dev: copy `.env.example` to `.env`.

## LLM Backend

Set `OPENROUTER_API_KEY` for OpenRouter (free DeepSeek/Gemini) or `OPENAI_API_KEY` for OpenAI.
If both are set, OpenRouter takes priority.

## GPT Profiles

| Profile | Use | Tone |
|---------|-----|------|
| `default` | TG channel posts | Expert, analytical, references PKU/NBU |
| `social` | Twitter/Threads | Provocative, system-bullying, drives engagement |

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
    source_id, source_type, origin_chat, origin_text, origin_url?
    red_text, twitter_text, post_targets (tg|social|both)
    status: INGESTED → RED_READY → POSTED | SKIPPED
    ingest_message_id, review_message_id, twitter_post_id
    posted_at

  posts/{draft_id}          ← knowledge base for future agents
    tg_text, twitter_text, origin_text, source_id, source_type, posted_at
```

## First-time Bootstrap

```bash
# 1. Seed workspace + sources
export WORKSPACE_ID=fop
export WORKSPACE_TITLE=FOP
export GROUP_CHAT_ID=-1003277785413
export INGEST_THREAD_ID=357
export REVIEW_THREAD_ID=358
export PUBLISH_CHANNEL_ID=@aifopukr
export GPT_PROFILE=default
export SOURCE_CHATS=@nbu_ua,@tax_gov_ua,@verkhovnaradaukrainy,@Minfin_com_ua,@bu911

python -m scripts.init_firestore

# 2. Set Telegram webhook
curl -X POST "https://api.telegram.org/bot$TG_BOT_TOKEN/setWebhook" \
  -d "url=https://APPROVER_URL/telegram/webhook" \
  -d "secret_token=$TG_BOT_TOKEN"

# 3. Run ingest twice (second run should fetch ~0 new messages)
gcloud run jobs execute ingest --region us-central1 --wait
gcloud run jobs execute ingest --region us-central1 --wait
```

## Pub/Sub Setup

```bash
gcloud pubsub topics create tg-raw-ingested

gcloud pubsub subscriptions create tg-raw-ingested-processor \
  --topic tg-raw-ingested \
  --push-endpoint https://PROCESSOR_URL/pubsub/push \
  --push-auth-service-account PROCESSOR_PUSH_SA@PROJECT_ID.iam.gserviceaccount.com \
  --push-auth-token-audience https://PROCESSOR_URL
```

## Secrets Bootstrap

```bash
scripts/bootstrap-secrets.sh <gcp-project-id>
```

## CI/CD

GitHub Actions (`workflow_dispatch` only). Required secrets: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`. Required variables: see `README.architecture.md`.

## Tests

```bash
pip install -r requirements-test.txt
pytest tests/ -v
```

93 tests covering: ingest utils, processor utils, approver utils, web enricher, GPT profiles, processor endpoint, approver endpoint.
