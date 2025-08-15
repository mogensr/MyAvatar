# BLOCK 1: Imports and Setup
import streamlit as st
import requests
import feedparser
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter
from dotenv import load_dotenv
import logging

# GROUP 1A: Load environment + setup logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GROUP 1B: Section keyword mappings
SECTION_MAPPINGS = {
    "macro": {
        "keywords": ["economy", "federal reserve", "inflation", "GDP", "central bank", "monetary policy"]
    },
    "corporate": {
        "keywords": ["earnings", "quarterly results", "merger", "acquisition", "CEO", "stock market"]
    },
    "market": {
        "keywords": ["stock market", "trading", "dow jones", "SP 500", "nasdaq", "market analysis"]
    }
}
# BLOCK 2: Main Article Fetcher

def fetch_articles_by_section(section: Optional[str]) -> List[Dict]:
    try:
        if section is None:
            logger.info("Fetching all sections")
            combined = []
            for sec in SECTION_MAPPINGS:
                combined += fetch_articles_by_section(sec)
            return dedupe_and_cache(combined)

        section = section.lower().strip().replace("news", "")
        if section.startswith("macro"):
            section = "macro"
        elif section.startswith("corporate"):
            section = "corporate"
        else:
            section = "market"

        logger.info(f"Fetching section: {section}")
        api_articles = fetch_api_articles(section)
        rss_articles = fetch_rss_articles(section)
        return dedupe_and_cache(api_articles + rss_articles)

    except Exception as e:
        logger.error(f"Error fetching articles: {e}")
        return []
# BLOCK 3: API Article Fetching

@st.cache_data(ttl=1800)
def fetch_api_articles(section: str) -> List[Dict]:
    articles = []
    apis = {
        'gnews': os.getenv('GNEWS_API_KEY', ''),
        'mediastack': os.getenv('MEDIASTACK_API_KEY', '')
    }

    for name, key in apis.items():
        if key:
            try:
                if name == 'gnews':
                    articles += normalize_articles(fetch_gnews_articles(key, section), name)
                elif name == 'mediastack':
                    articles += normalize_articles(fetch_mediastack_articles(key, section), name)
            except Exception as e:
                logger.warning(f"{name} failed: {e}")
    return articles

def fetch_gnews_articles(api_key, section):
    query = " OR ".join(SECTION_MAPPINGS[section]["keywords"])
    url = "https://gnews.io/api/v4/search"
    params = {'token': api_key, 'q': query, 'lang': 'en', 'max': 20}
    r = requests.get(url, params=params, timeout=30)
    return r.json().get("articles", []) if r.status_code == 200 else []

def fetch_mediastack_articles(api_key, section):
    query = ",".join(SECTION_MAPPINGS[section]["keywords"])
    url = "http://api.mediastack.com/v1/news"
    params = {'access_key': api_key, 'keywords': query, 'languages': 'en', 'limit': 20}
    r = requests.get(url, params=params, timeout=30)
    return r.json().get("data", []) if r.status_code == 200 else []

# BLOCK 4: RSS Article Fetching

def fetch_rss_articles(section: str) -> List[Dict]:
    rss_feeds = get_rss_feeds_for_section(section)
    articles = []

    for feed in rss_feeds:
        try:
            articles += parse_rss_feed(feed['url'])
        except Exception as e:
            logger.warning(f"RSS error ({feed['url']}): {e}")
    return articles

def get_rss_feeds_for_section(section: str) -> List[Dict]:
    feeds = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    ]
    return [{"url": url} for url in feeds]

def parse_rss_feed(url: str) -> List[Dict]:
    feed = feedparser.parse(url)
    if hasattr(feed, "status") and feed.status != 200:
        return []
    return [{
        "title": entry.get("title", ""),
        "summary": entry.get("summary", ""),
        "url": entry.get("link", ""),
        "date": entry.get("published", ""),
        "source": feed.feed.get("title", "RSS"),
        "type": "rss"
    } for entry in feed.entries[:20]]
# BLOCK 5: Normalization + Deduplication

def normalize_articles(articles: List[Dict], source: str) -> List[Dict]:
    normalized = []
    for a in articles:
        try:
            summary = a.get("description") or a.get("summary") or a.get("content", "")[:200]
            normalized.append({
                "id": f"{source}_{hash(a.get('url', '') + a.get('title', ''))}",
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "author": a.get("author", ""),
                "source": a.get("source", {}).get("name", source) if isinstance(a.get("source"), dict) else source,
                "published_at": a.get("publishedAt") or a.get("date") or datetime.now().isoformat(),
                "summary": summary,
                "type": "api",
                "category": "financial"
            })
        except:
            continue
    return normalized

def dedupe_and_cache(articles: List[Dict]) -> List[Dict]:
    seen, unique = set(), []
    for a in articles:
        uid = a.get("url", "") or a.get("title", "")
        if uid not in seen:
            unique.append(a)
            seen.add(uid)

    try:
        article_cache.add_articles(unique)
    except Exception as e:
        logger.warning(f"Cache error: {e}")

    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return unique[:50]

