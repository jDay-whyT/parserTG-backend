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


def post_tweet(text: str) -> str | None:
    client = get_twitter_client()
    if client is None:
        logger.warning("twitter_client_unavailable")
        return None
    response = client.create_tweet(text=text)
    tweet_id = str(response.data["id"])
    logger.info("twitter_post_success", extra={"tweet_id": tweet_id})
    return tweet_id
