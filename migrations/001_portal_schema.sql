-- ============================================================
-- 001_portal_schema.sql
-- 포털 유저 / 채널 / 영상신청 스키마
-- Supabase SQL Editor 에서 실행하세요.
-- ============================================================

-- 1. portal_users: 포털 로그인 계정 (이메일 기반)
CREATE TABLE IF NOT EXISTS portal_users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      TEXT UNIQUE NOT NULL,
    name       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. portal_channels: 유저 소유 채널 (owner_id FK)
CREATE TABLE IF NOT EXISTS portal_channels (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id     UUID NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
    channel_name TEXT NOT NULL,
    platform     TEXT NOT NULL DEFAULT 'youtube',  -- youtube / naver / kakao
    channel_url  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / blocked
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portal_channels_owner ON portal_channels(owner_id);

-- 3. portal_videos: 채널이 신청한 작품 (channel_id → portal_channels, work_id → works)
CREATE TABLE IF NOT EXISTS portal_videos (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id     UUID NOT NULL REFERENCES portal_channels(id) ON DELETE CASCADE,
    work_id        INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    request_status TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
    drive_link     TEXT,
    requested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at    TIMESTAMPTZ,
    UNIQUE (channel_id, work_id)   -- 중복 신청 방지
);

CREATE INDEX IF NOT EXISTS idx_portal_videos_channel ON portal_videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_portal_videos_work    ON portal_videos(work_id);

-- ============================================================
-- 테스트 데이터
-- ============================================================

-- 테스트 유저
INSERT INTO portal_users (email, name)
VALUES ('hoyoungy2@gmail.com', '호영')
ON CONFLICT (email) DO NOTHING;

-- 테스트 채널 2개
INSERT INTO portal_channels (owner_id, channel_name, platform, status)
SELECT id, '루나 숏폼', 'youtube', 'approved'
FROM   portal_users WHERE email = 'hoyoungy2@gmail.com'
ON CONFLICT DO NOTHING;

INSERT INTO portal_channels (owner_id, channel_name, platform, status)
SELECT id, '네이버 클립랩', 'naver', 'approved'
FROM   portal_users WHERE email = 'hoyoungy2@gmail.com'
ON CONFLICT DO NOTHING;
