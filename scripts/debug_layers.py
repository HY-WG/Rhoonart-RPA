# -*- coding: utf-8 -*-
"""Layer A 대안 및 Layer B 드라마명 추출 전략 검증."""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
import requests
from datetime import datetime, timedelta, timezone

key  = os.environ["YOUTUBE_API_KEY"]
BASE = "https://www.googleapis.com/youtube/v3"

def search_v(label, **params):
    params["key"] = key
    r = requests.get(f"{BASE}/search", params=params, timeout=15)
    d = r.json()
    items = d.get("items", [])
    print(f"\n[{label}] status={r.status_code}  items={len(items)}")
    if d.get("error"):
        print("  ERROR:", json.dumps(d["error"], ensure_ascii=False)[:300])
    channels = set()
    for it in items:
        cid = it.get("snippet", {}).get("channelId") or it.get("id", {}).get("channelId", "")
        title = it.get("snippet", {}).get("title", "")[:55]
        if cid not in channels:
            channels.add(cid)
            print(f"  ch={cid[-10:]}  {title}")
    time.sleep(0.3)
    return items

# ── Layer A 대안: type=channel 직접 채널 검색 ─────────────────────────────
print("==============================")
print("Layer A 대안: type=channel 검색")
print("==============================")
for q in ["드라마 클립 채널", "영화 명장면 채널", "drama clip shorts"]:
    search_v(f"channel q='{q}'", part="snippet", type="channel",
             q=q, regionCode="KR", relevanceLanguage="ko",
             maxResults=10, order="relevance")

# ── Layer B: 드라마명 추출을 위한 clip 영상 검색 ─────────────────────────
print()
print("==============================")
print("Layer B: 드라마명 추출 (에피소드 마커 있는 경우만)")
print("==============================")
published_after = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")

import re
def extract_drama_with_episode(video_title: str):
    """에피소드 마커(N화, EP N, 시즌N)가 있을 때만 드라마명 추출."""
    HAS_EP = re.compile(
        r'\d+\s*(?:화|회|부)|EP\.?\s*\d+|E\d+(?!\d)|Ep\s*\d+|시즌\s*\d+|Season\s*\d+',
        re.IGNORECASE
    )
    if not HAS_EP.search(video_title):
        return None
    PREFIX = re.compile(
        r'^\s*[\[【]?(?:tvN|JTBC|KBS\d*|MBC|SBS|OCN|EBS|채널A|'
        r'넷플릭스|Netflix|왓챠|Watcha|티빙|Tving|웨이브|Wavve)[\]】]?\s*[|·\-]?\s*'
        r'(?:드라마|영화|예능)?\s*', re.IGNORECASE)
    EP_RE = re.compile(
        r'\s*(?:\(?\d+\s*(?:화|회|부)\)?|EP\.?\s*\d+|E\d+|Ep\s*\d+|'
        r'시즌\s*\d+|Season\s*\d+|S\d+E\d+|클립|명장면|하이라이트|Highlight|Clip|모음|티저|'
        r'예고편?|OST|리뷰|분석|해설|결말|엔딩|스포|레전드|full\s*ver).*$',
        re.IGNORECASE)
    text = PREFIX.sub("", video_title).strip()
    text = EP_RE.sub("", text).strip(" |-·[]【】「」")
    if len(text) >= 2 and re.search(r"[가-힣]{2,}", text):
        return text
    return None

for kw in ["드라마 명장면", "한국 드라마 클립"]:
    items = search_v(f"drama clip q='{kw}' published<6m", part="snippet", type="video",
                     videoDuration="short", q=kw, regionCode="KR",
                     relevanceLanguage="ko", maxResults=25, order="viewCount",
                     publishedAfter=published_after)
    titles_with_ep = []
    for it in items:
        raw = it["snippet"]["title"]
        t = extract_drama_with_episode(raw)
        if t:
            titles_with_ep.append(t)
    uniq = list(dict.fromkeys(titles_with_ep))
    print(f"  → 에피소드 마커 있는 드라마명 ({len(uniq)}개): {uniq}")
