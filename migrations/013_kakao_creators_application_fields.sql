-- Migration 013: extend kakao_creators for Kakao shortform application form

begin;

alter table public.kakao_creators
  add column if not exists onboarding_round text,
  add column if not exists partner_name text,
  add column if not exists operation_enabled text,
  add column if not exists whitelist_enabled text,
  add column if not exists crawling_collection integer,
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
  add column if not exists sync_enabled text,
  add column if not exists zzalstudio_id text,
  add column if not exists onboarding_completed text,
  add column if not exists permission_status text,
  add column if not exists representative_sns_platform text,
  add column if not exists representative_sns_platform_other text,
  add column if not exists channel_name text,
  add column if not exists youtube_kakao_sync_wanted text,
  add column if not exists identity_or_business_file_id text,
  add column if not exists identity_or_business_file_name text,
  add column if not exists identity_or_business_file_url text,
  add column if not exists bankbook_file_id text,
  add column if not exists bankbook_file_name text,
  add column if not exists bankbook_file_url text;

comment on column public.kakao_creators.onboarding_round is 'Onboarding round';
comment on column public.kakao_creators.partner_name is 'Partner name';
comment on column public.kakao_creators.operation_enabled is 'Operation enabled flag';
comment on column public.kakao_creators.whitelist_enabled is 'Whitelist enabled flag';
comment on column public.kakao_creators.creator_name is 'Creator name';
comment on column public.kakao_creators.crawling_collection is 'Crawling collection count';
comment on column public.kakao_creators.kakao_channel_name is 'KakaoTalk channel name';
comment on column public.kakao_creators.kakao_email is 'Kakao email address';
comment on column public.kakao_creators.account_type is 'Kakao shortform account type';
comment on column public.kakao_creators.channel_link is 'Representative channel link';
comment on column public.kakao_creators.youtube_channel_id is 'YouTube channel ID';
comment on column public.kakao_creators.subscriber_count is 'Subscriber count';
comment on column public.kakao_creators.scale is 'Creator scale';
comment on column public.kakao_creators.category is 'Category';
comment on column public.kakao_creators.sub_category is 'Sub category';
comment on column public.kakao_creators.account_classification is 'Account classification';
comment on column public.kakao_creators.sync_enabled is 'YouTube-Kakao sync enabled flag';
comment on column public.kakao_creators.zzalstudio_id is 'Zzalstudio ID';
comment on column public.kakao_creators.onboarding_completed is 'Onboarding completed flag';
comment on column public.kakao_creators.permission_status is 'Permission status';
comment on column public.kakao_creators.note is 'Notes';
comment on column public.kakao_creators.representative_sns_platform is 'Representative SNS platform';
comment on column public.kakao_creators.channel_name is 'Application form channel name';
comment on column public.kakao_creators.youtube_kakao_sync_wanted is 'YouTube-Kakao shortform sync preference';
comment on column public.kakao_creators.identity_or_business_file_url is 'Identity or business registration Google Drive URL';
comment on column public.kakao_creators.bankbook_file_url is 'Bankbook copy Google Drive URL';

commit;
