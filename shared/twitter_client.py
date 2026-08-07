from __future__ import annotations

import logging

import tweepy

from shared.settings import settings

logger = logging.getLogger("twitter_client")

_client: tweepy.Client | None = None


def get_twitter_client() -> tweepy.Client | None:
    global _client
    if _client is not None:
        return _client
    if not all([
        settings.twitter_api_key,
        settings.twitter_api_secret,
        settings.twitter_access_token,
        settings.twitter_access_secret,
    ]):
        return None
    _client = tweepy.Client(
        consumer_key=settings.twitter_api_key,
        consumer_secret=settings.twitter_api_secret,
        access_token=settings.twitter_access_token,
        access_token_secret=settings.twitter_access_secret,
    )
    return _client


TWEET_LIMIT = 280
_THREAD_SUFFIX_RESERVE = 6  # room for " 12/34"


def split_tweet_thread(text: str, limit: int = TWEET_LIMIT) -> list[str]:
    words = text.split()
    max_len = limit - _THREAD_SUFFIX_RESERVE
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) > max_len:
            if current:
                chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    if len(chunks) <= 1:
        return [text] if text else []
    total = len(chunks)
    return [f"{chunk} {i}/{total}" for i, chunk in enumerate(chunks, start=1)]


def post_tweet(text: str) -> str | None:
    client = get_twitter_client()
    if client is None:
        logger.warning("twitter_client_unavailable")
        return None
    if len(text) <= TWEET_LIMIT:
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        logger.info("twitter_post_success", extra={"tweet_id": tweet_id})
        return tweet_id
    return _post_thread(client, text)


def _post_thread(client: tweepy.Client, text: str) -> str | None:
    parts = split_tweet_thread(text)
    root_id: str | None = None
    reply_to: str | None = None
    for part in parts:
        response = client.create_tweet(text=part, in_reply_to_tweet_id=reply_to)
        reply_to = str(response.data["id"])
        if root_id is None:
            root_id = reply_to
    logger.info("twitter_thread_post_success", extra={"root_tweet_id": root_id, "parts": len(parts)})
    return root_id
