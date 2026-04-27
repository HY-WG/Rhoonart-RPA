# -*- coding: utf-8 -*-
"""드라마명 추출 함수 검증 스크립트.

리팩토링으로 _extract_drama_name 이 두 함수로 분리됨:
  - _extract_drama_name_from_hashtag  : #태그 패턴에서 추출
  - _extract_drama_name_with_episode  : 에피소드 마커(N화/EP N/시즌N)에서 추출

두 함수를 순차 시도하는 로컬 wrapper(_extract_drama_name)를 사용.

변경된 기대값:
  - "tvN 눈물의 여왕 명장면 모음 TOP10"
    에피소드 마커·해시태그 없음 → None (구 함수: "눈물의 여왕" 반환했으나 현 아키텍처에서 제거됨)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from src.core.crawlers.youtube_shorts_crawler import (
    _extract_drama_name_from_hashtag,
    _extract_drama_name_with_episode,
)


def _extract_drama_name(title: str):
    """hashtag → episode 순으로 시도하는 로컬 wrapper."""
    return _extract_drama_name_from_hashtag(title) or _extract_drama_name_with_episode(title)


tests = [
    # (입력 제목,                              기대값,                  사용 함수)
    ("눈물의 여왕 16화 명장면",           "눈물의 여왕",       "episode"),
    ("[tvN] 졸업 6화 하이라이트",          "졸업",              "episode"),
    ("MBC 드라마 연인 E12 클립",           "연인",              "episode"),
    ("오징어게임 시즌2 완전 분석",         "오징어게임",        "episode"),
    ("폭싹 속았수다 7화 클립 모음",        "폭싹 속았수다",     "episode"),
    ("JTBC 이재, 곧 죽습니다 EP8",         "이재, 곧 죽습니다", "episode"),
    ("김켈리 vlog 일상",                   None,                "none"),
    ("[넷플릭스] 정년이 5화 레전드씬",     "정년이",            "episode"),
    # 에피소드 마커·해시태그 없음 → None (리팩토링 이후 변경된 케이스)
    ("tvN 눈물의 여왕 명장면 모음 TOP10",  None,                "none"),
]

all_pass = True
for raw, expected, note in tests:
    got = _extract_drama_name(raw)
    ok = got == expected
    if not ok:
        all_pass = False
    status = "OK  " if ok else "FAIL"
    print(f"  {status}  [{note:7}]  {raw:<45} → {got!r:25} (expected {expected!r})")

print()
print("전체 통과" if all_pass else "일부 실패 — 패턴 보정 필요")
