-- Migration 014: add standard Kakao creator list fields

begin;

alter table public.kakao_creators
  add column if not exists batch_number text,
  add column if not exists partner_name text,
  add column if not exists is_active boolean,
  add column if not exists is_whitelisted boolean,
  add column if not exists creator_name text,
  add column if not exists is_crawled boolean,
  add column if not exists kakao_channel_name text,
  add column if not exists kakao_email text,
  add column if not exists account_type text,
  add column if not exists channel_link text,
  add column if not exists youtube_channel_id text,
  add column if not exists subscriber_count bigint,
  add column if not exists scale text,
  add column if not exists category text,
  add column if not exists sub_category text,
  add column if not exists account_classification text,
  add column if not exists is_linked boolean,
  add column if not exists jjal_studio_id text,
  add column if not exists is_onboarded boolean,
  add column if not exists permission_status text,
  add column if not exists remarks text;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'onboarding_round'
  ) then
    execute 'update public.kakao_creators set batch_number = coalesce(batch_number, onboarding_round)';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'operation_enabled'
  ) then
    execute 'update public.kakao_creators set is_active = coalesce(is_active, operation_enabled = ''O'')';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'whitelist_enabled'
  ) then
    execute 'update public.kakao_creators set is_whitelisted = coalesce(is_whitelisted, whitelist_enabled = ''O'')';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'crawling_collection'
  ) then
    execute 'update public.kakao_creators set is_crawled = coalesce(is_crawled, crawling_collection is not null and crawling_collection > 0)';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'channel_name'
  ) then
    execute 'update public.kakao_creators set kakao_channel_name = coalesce(kakao_channel_name, channel_name)';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'kakao_channel'
  ) then
    execute 'update public.kakao_creators set kakao_channel_name = coalesce(kakao_channel_name, kakao_channel)';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'contact_email'
  ) then
    execute 'update public.kakao_creators set kakao_email = coalesce(kakao_email, contact_email)';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'sync_enabled'
  ) then
    execute 'update public.kakao_creators set is_linked = coalesce(is_linked, sync_enabled = ''O'')';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'zzalstudio_id'
  ) then
    execute 'update public.kakao_creators set jjal_studio_id = coalesce(jjal_studio_id, zzalstudio_id)';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'onboarding_completed'
  ) then
    execute 'update public.kakao_creators set is_onboarded = coalesce(is_onboarded, onboarding_completed = ''O'')';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'kakao_creators' and column_name = 'note'
  ) then
    execute 'update public.kakao_creators set remarks = coalesce(remarks, note)';
  end if;
end $$;

comment on column public.kakao_creators.batch_number is '입점 차수';
comment on column public.kakao_creators.partner_name is '제휴사명';
comment on column public.kakao_creators.is_active is '운영 여부';
comment on column public.kakao_creators.is_whitelisted is '화이트리스트 사용 여부';
comment on column public.kakao_creators.creator_name is '크리에이터명';
comment on column public.kakao_creators.is_crawled is '크롤링 수집';
comment on column public.kakao_creators.kakao_channel_name is '카카오톡 채널명';
comment on column public.kakao_creators.kakao_email is '카카오 email 주소';
comment on column public.kakao_creators.account_type is '계정 유형';
comment on column public.kakao_creators.channel_link is '채널 링크';
comment on column public.kakao_creators.youtube_channel_id is '유튜브 채널 ID';
comment on column public.kakao_creators.subscriber_count is '구독자 수';
comment on column public.kakao_creators.scale is '규모';
comment on column public.kakao_creators.category is '카테고리';
comment on column public.kakao_creators.sub_category is '세부 카테고리';
comment on column public.kakao_creators.account_classification is '계정 구분';
comment on column public.kakao_creators.is_linked is '연동 여부';
comment on column public.kakao_creators.jjal_studio_id is '짤스튜디오ID';
comment on column public.kakao_creators.is_onboarded is '온보딩 완료';
comment on column public.kakao_creators.permission_status is '권한 상태';
comment on column public.kakao_creators.remarks is '비고';

commit;
