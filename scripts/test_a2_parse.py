# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from src.handlers.a2_work_approval import parse_slack_message

tests = [
    ('채널: "유호영" 의 신규 영상 사용 요청이 있습니다.\n21세기 대군부인',  ('유호영',  '21세기 대군부인')),
    ('채널: \u201c홍길동\u201d 의 신규 영상 사용 요청이 있습니다.\n눈물의 여왕', ('홍길동', '눈물의 여왕')),
    ('채널: "김채널" 의 신규 영상 사용 요청이 있습니다.\n오징어게임', ('김채널', '오징어게임')),
]

all_pass = True
for text, expected in tests:
    got = parse_slack_message(text)
    ok = got == expected
    if not ok:
        all_pass = False
    print(f"  {'OK' if ok else 'FAIL'}  got={got!r}  expected={expected!r}")

print()
print("전체 통과" if all_pass else "일부 실패 — 패턴 확인 필요")
