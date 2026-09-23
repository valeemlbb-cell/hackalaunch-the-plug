"""Shared vocabulary so a brief written in prose and a creator tagged by a scout end up
speaking the same language.

Two things live here:

  TOPICS     canonical topic -> the words that imply it. A brief saying "we built a
             budgeting app" and a creator tagged `personal_finance` must collide.
  RELATED    canonical topic -> neighbours that count as a partial (0.5) match, because
             a crypto audience is a plausible fintech audience but not a cooking one.

Deliberately small and hand-curated. An embedding model would cover more words, but it
also invents matches nobody can defend to a founder, and the brief asks for explanations.
Adding a topic is a two-line edit; see docs/MATCHING.md.
"""
from __future__ import annotations

import re

TOPICS: dict = {
    "personal_finance": ("finance", "budgeting", "budget app", "saving", "savings", "investing",
                         "investment", "money", "keuangan", "nabung", "financial", "wealth", "frugal"),
    "crypto": ("crypto", "web3", "defi", "token", "solana", "ethereum", "bitcoin", "nft",
               "onchain", "on-chain", "wallet", "airdrop", "blockchain"),
    "startup": ("startup", "founder", "saas", "b2b", "indie hacker", "bootstrapped", "product hunt",
                "venture", "pre-seed", "seed round"),
    "productivity": ("productivity", "workflow", "note taking", "second brain", "time management",
                     "focus", "todo", "planner", "automation"),
    "developer_tools": ("developer", "devtool", "api", "sdk", "open source", "programming",
                        "coding", "engineer", "cli", "framework", "library"),
    "ai": ("ai", "artificial intelligence", "llm", "machine learning", "chatgpt", "claude",
           "agent", "prompt", "generative"),
    "gaming": ("gaming", "game", "gamer", "esports", "stream", "twitch", "roblox", "minecraft"),
    # "running" is deliberately absent: briefs say "running Oct 1 to Oct 21" far more often
    # than they mean the sport. "run club" is the unambiguous form.
    "fitness": ("fitness", "gym", "workout", "training", "run club", "health", "olahraga"),
    "beauty": ("beauty", "skincare", "makeup", "cosmetic", "skin", "kecantikan"),
    "food": ("food", "cooking", "recipe", "restaurant", "kuliner", "masak", "coffee"),
    "travel": ("travel", "trip", "backpacking", "destination", "wisata", "jalan-jalan"),
    "education": ("education", "learning", "course", "tutorial", "study", "student", "kuliah",
                  "belajar", "edukasi"),
    "parenting": ("parenting", "kids", "family", "toddler", "orang tua", "anak"),
    "career": ("career", "job", "hiring", "resume", "interview", "freelance", "karir", "loker"),
    "fashion": ("fashion", "outfit", "streetwear", "style", "thrift"),
    "podcast_talk": ("podcast", "interview", "long form", "talk show", "obrolan"),
    "comedy": ("comedy", "humour", "humor", "sketch", "funny", "lucu"),
    "news_commentary": ("news", "commentary", "politics", "analysis", "berita"),
    "home_diy": ("diy", "home", "interior", "renovation", "furniture", "rumah"),
    "automotive": ("automotive", "car", "motorcycle", "otomotif", "mobil", "motor"),
}

RELATED: dict = {
    "personal_finance": ("crypto", "career", "startup"),
    "crypto": ("personal_finance", "developer_tools", "ai", "startup"),
    "startup": ("developer_tools", "ai", "productivity", "career"),
    "productivity": ("startup", "developer_tools", "education", "ai"),
    "developer_tools": ("ai", "startup", "productivity"),
    "ai": ("developer_tools", "productivity", "startup"),
    "gaming": ("comedy", "podcast_talk"),
    "fitness": ("food", "beauty"),
    "beauty": ("fashion", "fitness"),
    "food": ("travel", "home_diy", "fitness"),
    "travel": ("food", "fashion"),
    "education": ("career", "productivity", "parenting"),
    "parenting": ("education", "home_diy", "food"),
    "career": ("education", "startup", "personal_finance"),
    "fashion": ("beauty", "comedy"),
    "podcast_talk": ("news_commentary", "comedy", "education"),
    "comedy": ("gaming", "podcast_talk"),
    "news_commentary": ("podcast_talk", "career"),
    "home_diy": ("food", "parenting"),
    "automotive": ("gaming", "home_diy"),
}

TOPIC_LABELS: dict = {
    "personal_finance": {"en": "personal finance", "id": "keuangan pribadi"},
    "crypto": {"en": "crypto", "id": "kripto"},
    "startup": {"en": "startups", "id": "startup"},
    "productivity": {"en": "productivity", "id": "produktivitas"},
    "developer_tools": {"en": "developer tools", "id": "tools developer"},
    "ai": {"en": "AI", "id": "AI"},
    "gaming": {"en": "gaming", "id": "gaming"},
    "fitness": {"en": "fitness", "id": "kebugaran"},
    "beauty": {"en": "beauty", "id": "kecantikan"},
    "food": {"en": "food", "id": "kuliner"},
    "travel": {"en": "travel", "id": "traveling"},
    "education": {"en": "learning", "id": "edukasi"},
    "parenting": {"en": "parenting", "id": "parenting"},
    "career": {"en": "work and careers", "id": "kerja dan karir"},
    "fashion": {"en": "fashion", "id": "fashion"},
    "podcast_talk": {"en": "long-form conversation", "id": "obrolan panjang"},
    "comedy": {"en": "comedy", "id": "komedi"},
    "news_commentary": {"en": "news commentary", "id": "komentar berita"},
    "home_diy": {"en": "home and DIY", "id": "rumah dan DIY"},
    "automotive": {"en": "cars", "id": "otomotif"},
}


def topic_label(topic: str, language: str = "en") -> str:
    return TOPIC_LABELS.get(topic, {}).get(language, topic.replace("_", " "))


PLATFORM_WORDS: dict = {
    "tiktok": ("tiktok", "tik tok"),
    "youtube": ("youtube", "yt", "shorts"),
    "instagram": ("instagram", "ig", "reels"),
    # No bare "x": a brief that says "2 x TikTok" is not asking for Twitter.
    "x": ("twitter", "tweet", "x.com", "on x"),
    "podcast": ("podcast", "spotify", "apple podcasts"),
    "newsletter": ("newsletter", "substack", "beehiiv", "email list"),
    "twitch": ("twitch",),
    "linkedin": ("linkedin",),
}

GOAL_WORDS: dict = {
    "app_installs": ("install", "download", "app store", "play store"),
    "signups": ("signup", "sign-up", "sign up", "waitlist", "trial", "register", "beta"),
    "sales": ("sale", "sales", "revenue", "purchase", "buy", "conversion", "checkout", "order"),
    "community": ("community", "discord", "telegram", "members", "join the server"),
    "awareness": ("awareness", "reach", "impressions", "brand", "launch", "visibility"),
}

LANGUAGE_WORDS: dict = {
    "id": ("indonesian", "bahasa indonesia", "indonesia", "bahasa"),
    "en": ("english", "en-us", "us audience", "uk audience", "global english"),
    "es": ("spanish", "espanol", "español", "latam"),
    "pt": ("portuguese", "brazil", "brasil"),
    "hi": ("hindi", "india"),
    "vi": ("vietnamese", "vietnam"),
    "th": ("thai", "thailand"),
    "tl": ("tagalog", "filipino", "philippines"),
}

GEO_WORDS: dict = {
    "ID": ("indonesia", "jakarta", "bandung", "surabaya"),
    "US": ("united states", "usa", "u.s.", "america", "us market"),
    "GB": ("united kingdom", "uk", "britain", "london"),
    "SG": ("singapore",),
    "MY": ("malaysia", "kuala lumpur"),
    "IN": ("india", "mumbai", "bangalore"),
    "BR": ("brazil", "brasil"),
    "GLOBAL": ("global", "worldwide", "international", "anywhere"),
}

_WORD_RE = re.compile(r"[a-z0-9\-']+")
_PHRASE_CACHE: dict = {}


def normalise(text: str) -> str:
    return f" {(text or '').lower()} "


def tokens(text: str) -> list:
    return _WORD_RE.findall((text or "").lower())


def _phrase_re(phrase: str):
    """Whole-word match with a tolerated plural.

    'ai' must not fire on 'raid' and 'car' must not fire on 'care about', so both ends are
    anchored on a word boundary. A single trailing 's' is allowed, because briefs say
    "signups" and "installs" while the vocabulary lists the singular.
    """
    pattern = _PHRASE_CACHE.get(phrase)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(phrase.strip()) + r"s?(?![a-z0-9])")
        _PHRASE_CACHE[phrase] = pattern
    return pattern


def contains(text: str, phrase: str) -> bool:
    return bool(_phrase_re(phrase).search(normalise(text)))


def detect_topics(text: str, limit: int = 8) -> list:
    """Canonical topics present in free text, strongest first.

    Score = number of distinct trigger phrases hit, so "crypto crypto crypto" does not
    beat a brief that genuinely spans wallet + defi + solana.
    """
    haystack = normalise(text)
    hits = []
    for topic, words in TOPICS.items():
        matched = {w for w in words if _phrase_re(w).search(haystack)}
        if matched:
            hits.append((len(matched), topic))
    hits.sort(key=lambda pair: (-pair[0], pair[1]))
    return [topic for _, topic in hits[:limit]]


def topic_affinity(a: str, b: str) -> float:
    """1.0 same topic, 0.5 neighbouring topic, 0.0 unrelated."""
    if a == b:
        return 1.0
    if b in RELATED.get(a, ()) or a in RELATED.get(b, ()):
        return 0.5
    return 0.0


def detect_from_map(text: str, mapping: dict) -> list:
    haystack = normalise(text)
    return [key for key, words in mapping.items()
            if any(_phrase_re(w).search(haystack) for w in words)]


def count_from_map(text: str, mapping: dict) -> dict:
    """key -> how many distinct trigger phrases fired. Used to break goal ties."""
    haystack = normalise(text)
    out = {}
    for key, words in mapping.items():
        hits = sum(1 for w in words if _phrase_re(w).search(haystack))
        if hits:
            out[key] = hits
    return out
