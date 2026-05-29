# parserTG-backend — CLAUDE.md

## Project Overview

Content pipeline for **buhFOP** — автоматичний збір новин з Telegram каналів та веб-сайтів,
GPT-фільтрація, генерація постів у двох форматах, ручний апрув через TG бот, постинг у TG канал + Twitter.

**Продукт:** [@aifopukr](https://t.me/aifopukr) — контент про ФОП, ПКУ, НБУ, фінмоніторинг для українських підприємців.

---

## Tech Stack

- **Ingest:** Telethon (MTProto) — TG канали, CloakBrowser — веб-парсинг, twscrape — Twitter
- **Queue:** Google Pub/Sub
- **Storage:** Firestore (Native mode, `nam5`)
- **AI:** OpenRouter API (DeepSeek V3 / Gemini Flash — free tier) для фільтрації та генерації
- **Posting:** python-telegram-bot (TG канал), tweepy (Twitter)
- **Infra:** Google Cloud Run Jobs + Cloud Run Services + Cloud Scheduler
- **Secrets:** Google Secret Manager (ніяких ключів у коді або .env у репо)
- **Region:** `us-central1`

---

## Architecture

```
Sources
├── Telethon → @nbu_ua, @tax_gov_ua, @verkhovnaradaukrainy, @Minfin_com_ua, @bu911
├── CloakBrowser → buhgalter911.com (новини + аналітика)
└── twscrape → англомовний Twitter (CPA, tax advisors)
        ↓
   Pub/Sub (tg-raw-ingested)
        ↓
   Processor (Cloud Run Service)
   - GPT фільтр: high / medium / low confidence
   - low → skip (нічого не робити)
   - medium → надіслати адміну в TG на апрув
   - high → генерувати пости
        ↓
   Генерація двох версій (OpenRouter):
   - TG версія: експертна, з деталями, посилання на ПКУ/НБУ
   - Twitter версія: коротка, провокаційна, байтить
        ↓
   Approver (Cloud Run Service)
   - Telegram bot webhook — апрув/відхилення medium постів
   - Після апруву або для high → постинг
        ↓
   Posting:
   - TG канал @aifopukr
   - Twitter (Tweepy, free tier)
```

---

## Project Structure

```
parserTG-backend/
├── services/
│   ├── ingest/          # Telethon + CloakBrowser + twscrape
│   ├── processor/       # Pub/Sub handler, GPT фільтр, генерація
│   └── approver/        # TG bot webhook, постинг
├── shared/
│   ├── gpt_profiles.py  # GPT промпти (фільтр + генерація)
│   └── prompts.py       # Системні промпти
├── scripts/
│   ├── init_firestore.py
│   ├── check_firestore.py
│   └── bootstrap-secrets.sh
├── tools/
│   └── set_webhook.py
├── .github/workflows/   # CI/CD deploy
├── .env.example
├── requirements.txt
└── CLAUDE.md            # Цей файл
```

---

## Sources Detail

### 1. Telethon (існуючий)
Читає TG канали через MTProto user-client:
- `@nbu_ua` — НБУ офіційний
- `@tax_gov_ua` — ДПС офіційний
- `@verkhovnaradaukrainy` — Верховна Рада
- `@Minfin_com_ua` — Мінфін
- `@bu911` — buhgalter911 TG канал (анонси)

### 2. CloakBrowser (новий — `services/ingest/web_parser.py`)
Парсить buhgalter911.com з підпискою:
- Логін через форму (логін/пароль з Secret Manager)
- Зберігає куки в Secret Manager після кожної сесії
- Парсить `/uk/news/` та `/uk/analytics/` — тільки нові статті (по даті, новіші за `last_run` з Firestore)
- Повертає: `{url, title, text, published_at, category}`
- Якщо куки протухли — логіниться заново
- **Важливо:** запускати тільки як Cloud Run Job, без uvloop (`--loop asyncio`)
- Затримки між запитами 2-5 сек щоб не тригерити антибот

### 3. twscrape (новий — `services/ingest/twitter_parser.py`)
Парсить англомовний Twitter без офіційного API:
- Акаунти для парсингу: CPA, tax advisors, fintech (список у Firestore)
- Хештеги: `#taxlaw #accounting #VAT #smallbusiness #taxplanning`
- Ліміт: 20-30 твітів за запуск
- Твіти потрапляють у той самий Pub/Sub топік з міткою `source_type: twitter_en`
- Processor локалізує їх під UA контекст перед генерацією поста

---

## GPT Profiles (OpenRouter)

**Модель:** `deepseek/deepseek-chat-v3-0324:free` або `google/gemini-flash-1.5:free`

### Профіль: filter
Фільтрує вхідний контент:
```json
{
  "confidence": "high|medium|low",
  "reason": "коротко чому",
  "skip": false
}
```

**Критерії HIGH (автопост):**
- Зміни ставок ЄП/ЄСВ/ВЗ
- Нові дедлайни звітності
- Зміни лімітів груп ФОП
- Фінмоніторинг — нові правила НБУ
- Штрафи і перевірки ДПС
- Офіційні роз'яснення ДПС/Мінфін

**Критерії MEDIUM (на апрув):**
- Новини що непрямо стосуються ФОП (кредити, трудові відносини)
- Англомовний контент після локалізації
- Неоднозначні теми

**Критерії LOW (skip):**
- Політика без прив'язки до фінансів
- Війна/фронт
- Дублікат теми за останні 24г (перевіряти по Firestore)
- Загальні економічні новини без практичної цінності для ФОП

### Профіль: generate_tg
TG версія поста — експертна:
- Заголовок + суть + що це означає для ФОП
- Посилання на статтю ПКУ або постанову НБУ якщо є
- 200-400 символів
- Без хештегів

### Профіль: generate_twitter
Twitter/Threads версія — провокаційна:
- Крючок через цифру або факт
- 200-280 символів
- 2-3 хештеги (#ФОП #ПКУ #бухгалтерія)
- Питання або заклик в кінці

### Профіль: localize (для twitter_en)
Локалізація англомовного контенту:
- Замінити IRS→ДПС, VAT→ПДВ, LLC→ТОВ/ФОП, IRS audit→перевірка ДПС
- Зберегти суть і загальний принцип
- Додати UA контекст якщо є пряма аналогія
- Якщо аналогії немає — skip

---

## Posting

### TG канал
- `PUBLISH_CHANNEL_ID=@aifopukr`
- python-telegram-bot, send_message

### Twitter
- Tweepy, free tier (до 1500 твітів/міс)
- Ключі: `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` у Secret Manager

### Threads (майбутнє — V2)
- Meta Threads API, OAuth 2.0
- Додати коли буде вирішено питання з Meta Developer акаунтом

---

## Firestore Schema

```
workspaces/{WORKSPACE_ID}
  sources/{source_id}
    - type: "telegram" | "web" | "twitter"
    - username / url
    - last_run: timestamp
    - enabled: bool

  drafts/{draft_id}
    - source_type: "telegram" | "web" | "twitter_en"
    - raw_text: str
    - confidence: "high" | "medium" | "low"
    - status: "pending" | "approved" | "rejected" | "posted"
    - tg_text: str
    - twitter_text: str
    - created_at: timestamp
    - posted_at: timestamp | null

  posted_topics/  # дедуп по темі
    - topic_hash: str
    - created_at: timestamp
```

---

## Secrets (Secret Manager)

```
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELETHON_STRING_SESSION
OPENROUTER_API_KEY          # замість OPENAI_API_KEY
TG_BOT_TOKEN
BUHGALTER911_LOGIN
BUHGALTER911_PASSWORD
BUHGALTER911_COOKIES        # JSON, оновлюється після кожної сесії
TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_SECRET
TWSCRAPE_ACCOUNT_LOGIN      # акаунт для парсингу Twitter
TWSCRAPE_ACCOUNT_PASSWORD
```

---

## Environment Variables

```
WORKSPACE_ID=fop
GROUP_CHAT_ID=-1003277785413
INGEST_THREAD_ID=357
REVIEW_THREAD_ID=358
PUBLISH_CHANNEL_ID=@aifopukr
GPT_PROFILE=default
SOURCE_CHATS=@nbu_ua,@tax_gov_ua,@verkhovnaradaukrainy,@Minfin_com_ua,@bu911
PUBSUB_TOPIC=tg-raw-ingested
INGEST_LIMIT=50
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324:free
```

---

## Infrastructure (Cloud Run)

| Service | Type | Trigger | min-instances |
|---------|------|---------|---------------|
| ingest | Job | Cloud Scheduler (кожні 3г) | 0 |
| processor | Service | Pub/Sub push | 0 |
| approver | Service | Telegram webhook | 0 |

**Важливо:** всі сервіси з `min-instances=0` — instance 0, платимо тільки за час роботи.

---

## Coding Guidelines (Karpathy)

### 1. Think Before Coding
- Явно вказуй припущення. Якщо невизначено — питай.
- Якщо є простіший підхід — скажи.

### 2. Simplicity First
- Мінімум коду що вирішує задачу.
- Без спекулятивних фіч.
- Без абстракцій для одноразового коду.

### 3. Surgical Changes
- Торкайся тільки того що треба.
- Не "покращуй" сусідній код.
- Видаляй тільки те що ТВОЇ зміни зробили непотрібним.

### 4. Goal-Driven Execution
- Перетворюй задачі на верифіковані цілі.
- Для багатокрокових задач — спочатку план, потім виконання.

---

## Hard Limits

- Ніяких ключів у коді або .env у репо
- Логи — тільки технічні (помилки, latency). Ніколи вміст постів
- Не змішувати дані між workspace
- Не копіювати текст джерела дослівно — тільки переосмислення через GPT
- CloakBrowser тільки в Job, не в Service (uvloop конфлікт)
