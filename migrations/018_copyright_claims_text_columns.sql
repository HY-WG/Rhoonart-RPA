-- Migration 018: copyright_claims 에 channel_name / work_title 텍스트 컬럼 추가
-- channel_id / work_id 는 soft ref (FK 없음) 이므로 Supabase 자동 조인 불가.
-- 실행: Supabase Dashboard > SQL Editor

begin;

alter table public.copyright_claims
  add column if not exists channel_name text,
  add column if not exists work_title   text;

commit;
