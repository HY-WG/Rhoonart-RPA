"""네이버 클립 GraphQL 직접 HTTP POST 가능 여부 테스트.

가능하면 → requests 기반 고속 크롤러 설계 가능
불가하면 → Playwright browser context 유지
"""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests

TAG = "재벌집막내아들"
URL = "https://clip.naver.com/api/graphql"

QUERY = """
query ContentsQuery(
  $input: ContentsInput!
  $first: Int
  $after: String
  $sessionId: String
  $reverse: Boolean = false
  $sessionStartTime: Float
) {
  contents(
    input: $input
    first: $first
    after: $after
    sessionId: $sessionId
    reverse: $reverse
    sessionStartTime: $sessionStartTime
  ) {
    pageInfo {
      hasNextPage
      endCursor
      __typename
    }
    sessionId
    sessionStartTime
    __typename
    edges {
      cursor
      __typename
      node {
        __typename
        id
        mediaId
        mediaType
        title
        publishedTime
        count
        user {
          profileId
          nickname
          __typename
        }
        interaction {
          like { count __typename }
          comment { count __typename }
          __typename
        }
      }
    }
  }
}
"""

def test_direct(headers_variant: str, headers: dict):
    payload = {
        "operationName": "ContentsQuery",
        "variables": {
            "reverse": False,
            "input": {
                "recType": "AIRS",
                "airsArea": f"hashtag.{TAG}",
                "panelType": "page_tag",
            },
            "first": 18,
        },
        "extensions": {
            "clientLibrary": {"name": "@apollo/client", "version": "4.1.6"}
        },
        "query": QUERY,
    }

    try:
        resp = requests.post(URL, json=payload, headers=headers, timeout=15)
        print(f"\n[{headers_variant}] status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            edges = data.get("data", {}).get("contents", {}).get("edges", [])
            first_count = edges[0]["node"]["count"] if edges else None
            has_next = data.get("data", {}).get("contents", {}).get("pageInfo", {}).get("hasNextPage")
            print(f"  [OK] edges={len(edges)}, 첫 클립 count={first_count}, hasNextPage={has_next}")
            return True
        else:
            print(f"  [실패] body={resp.text[:300]}")
            return False
    except Exception as e:
        print(f"  [예외] {e}")
        return False


# 헤더 변형 3가지 테스트
variants = [
    ("최소 헤더", {
        "Content-Type": "application/json",
    }),
    ("Referer 포함", {
        "Content-Type": "application/json",
        "Referer": f"https://clip.naver.com/hashtag/{TAG}",
        "Origin": "https://clip.naver.com",
    }),
    ("브라우저 UA 완전 모사", {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Origin": "https://clip.naver.com",
        "Referer": f"https://clip.naver.com/hashtag/{TAG}",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "x-apollo-operation-name": "ContentsQuery",
        "apollo-require-preflight": "true",
    }),
]

for name, hdrs in variants:
    test_direct(name, hdrs)
    time.sleep(0.5)

print("\n테스트 완료.")
