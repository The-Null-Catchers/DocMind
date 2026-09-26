from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass

from fastapi import Request
from redis.asyncio import Redis

from ..config import Settings


@dataclass(frozen=True)
class RateRule:
    method: str
    pattern: re.Pattern[str]
    limit: int


RULES = [
    RateRule("POST", re.compile(r"^/api/v1/auth/login$"), 10),
    RateRule("POST", re.compile(r"^/api/v1/auth/register$"), 5),
    RateRule("POST", re.compile(r"^/api/v1/auth/password/forgot$"), 5),
    RateRule("POST", re.compile(r"^/api/v1/auth/email-verification/request$"), 5),
    RateRule("POST", re.compile(r"^/api/v1/documents/upload$"), 20),
    RateRule("POST", re.compile(r"^/api/v1/documents/[^/]+/reprocess$"), 10),
    RateRule("POST", re.compile(r"^/api/v1/search(?:/global)?$"), 60),
    RateRule("POST", re.compile(r"^/api/v1/conversations/[^/]+/messages/stream$"), 30),
    RateRule("POST", re.compile(r"^/api/v1/(summaries/generate|compare|extract|ai/selection|ai/table)$"), 20),
    RateRule("POST", re.compile(r"^/api/v1/exports$"), 20),
    RateRule("POST", re.compile(r"^/api/v1/exports/[^/]+/retry$"), 10),
    RateRule("POST", re.compile(r"^/api/v1/(flashcards|quizzes)/generate$"), 15),
]


class RateLimiter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._memory: dict[str, tuple[int, float]] = {}
        self._redis: Redis | None = None
        if settings.app_env.lower() in {"production", "staging"}:
            self._redis = Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
            )

    @staticmethod
    def _rule(request: Request) -> RateRule | None:
        for rule in RULES:
            if request.method == rule.method and rule.pattern.match(request.url.path):
                return rule
        return None

    @staticmethod
    def _identity(request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        if authorization:
            digest = hashlib.sha256(authorization.encode()).hexdigest()[:24]
            return f"auth:{digest}"
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        address = forwarded or (request.client.host if request.client else "unknown")
        return f"ip:{address}"

    async def check(self, request: Request) -> tuple[bool, int]:
        if not self.settings.rate_limit_enabled:
            return True, 0
        rule = self._rule(request)
        if not rule:
            return True, 0

        window = max(1, self.settings.rate_limit_window_seconds)
        bucket = int(time.time() // window)
        key = f"docmind:ratelimit:{rule.method}:{rule.pattern.pattern}:{self._identity(request)}:{bucket}"

        if self._redis is not None:
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, window + 1)
                return count <= rule.limit, window
            except Exception:
                # Keep protecting endpoints during Redis degradation without taking
                # the application down. /ready still reports Redis unavailable.
                pass

        now = time.monotonic()
        count, expires = self._memory.get(key, (0, now + window))
        if now >= expires:
            count, expires = 0, now + window
        count += 1
        self._memory[key] = (count, expires)

        # Opportunistic bounded cleanup.
        if len(self._memory) > 5000:
            self._memory = {
                item_key: value
                for item_key, value in self._memory.items()
                if value[1] > now
            }
        return count <= rule.limit, max(1, int(expires - now))
