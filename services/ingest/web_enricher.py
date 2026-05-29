from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger("web_enricher")

BUHGALTER911_URL_RE = re.compile(r"https?://(?:www\.)?buhgalter911\.com/\S+")
LOGIN_URL = "https://buhgalter911.com/uk/login/"
MIN_ARTICLE_CHARS = 300
FETCH_TIMEOUT_S = 45

_ARTICLE_SELECTORS = [
    "[itemprop='articleBody']",
    ".article-text",
    ".article-body",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".news-text",
    ".content-text",
    "article .text",
    ".full-text",
    "article",
    "main",
]

_LOGIN_INDICATORS = ["login", "увійти", "sign in", "авторизація", "зареєструватись", "передплат"]


def extract_buhgalter_url(text: str) -> str | None:
    match = BUHGALTER911_URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,)>\"'")


def _page_needs_login(html_content: str) -> bool:
    lower = html_content.lower()
    return any(s in lower for s in _LOGIN_INDICATORS)


async def _do_login(page: Any, login: str, password: str) -> None:
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20_000)
    for sel in ['input[type="email"]', 'input[name="email"]', 'input[name="login"]', "#email"]:
        if await page.query_selector(sel):
            await page.fill(sel, login)
            break
    for sel in ['input[type="password"]', 'input[name="password"]', "#password"]:
        if await page.query_selector(sel):
            await page.fill(sel, password)
            break
    for sel in ['button[type="submit"]', 'input[type="submit"]', ".login-btn", ".btn-login"]:
        if await page.query_selector(sel):
            await page.click(sel)
            break
    await page.wait_for_load_state("domcontentloaded", timeout=15_000)


async def _extract_article_text(page: Any) -> str:
    for sel in _ARTICLE_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) >= MIN_ARTICLE_CHARS:
                    return text
        except Exception:
            continue
    try:
        body = await page.query_selector("body")
        if body:
            return (await body.inner_text()).strip()
    except Exception:
        pass
    return ""


async def _fetch_article(url: str, login: str | None, password: str | None) -> str:
    from cloakbrowser import launch_async

    browser = await launch_async(headless=True)
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        html_content = await page.content()

        if login and password and _page_needs_login(html_content):
            logger.info("web_enricher_login_required", extra={"url": url})
            await _do_login(page, login, password)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        text = await _extract_article_text(page)
        return text
    finally:
        await browser.close()


async def enrich_payload(
    payload: dict,
    login: str | None = None,
    password: str | None = None,
) -> dict:
    origin_text = payload.get("origin_text") or ""
    url = extract_buhgalter_url(origin_text)
    if not url:
        return payload

    logger.info("web_enricher_start", extra={"url": url, "source_id": payload.get("source_id")})
    try:
        article_text = await asyncio.wait_for(
            _fetch_article(url, login=login, password=password),
            timeout=FETCH_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("web_enricher_timeout", extra={"url": url})
        return payload
    except ImportError:
        logger.warning("web_enricher_cloakbrowser_not_installed")
        return payload
    except Exception as exc:
        logger.warning("web_enricher_failed", extra={"url": url, "error": str(exc)})
        return payload

    if not article_text or len(article_text) <= len(origin_text):
        logger.info("web_enricher_no_gain", extra={"url": url, "article_len": len(article_text), "origin_len": len(origin_text)})
        return payload

    logger.info("web_enricher_success", extra={"url": url, "article_len": len(article_text)})
    enriched = dict(payload)
    enriched["origin_text"] = article_text
    enriched["origin_url"] = url
    enriched["source_type"] = "web"
    return enriched
