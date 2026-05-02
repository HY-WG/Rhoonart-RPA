alter table public.b2_content_catalog
  add column if not exists naver_report_enabled boolean not null default false;

update public.b2_content_catalog
set naver_report_enabled = identifier in ('1UBvb', 'dXdF9', 'NIvxu');

create index if not exists b2_content_catalog_naver_report_enabled_idx
  on public.b2_content_catalog (naver_report_enabled, identifier);
