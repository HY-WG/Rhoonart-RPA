begin;

alter table if exists public.channel rename to seed_channel;

alter index if exists public.channel_pkey rename to seed_channel_pkey;
alter index if exists public.idx_channel_channel_id rename to idx_seed_channel_channel_id;
alter index if exists public.idx_channel_url rename to idx_seed_channel_url;
alter index if exists public.idx_channel_platform rename to idx_seed_channel_platform;

do $$
begin
  if exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where n.nspname = 'public'
      and t.relname = 'seed_channel'
      and c.conname = 'channel_pkey'
  ) then
    alter table public.seed_channel rename constraint channel_pkey to seed_channel_pkey;
  end if;
end $$;

commit;
