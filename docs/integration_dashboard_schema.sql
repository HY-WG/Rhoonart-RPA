create table if not exists public.integration_runs (
    run_id text primary key,
    task_id text not null,
    title text not null,
    payload jsonb not null default '{}'::jsonb,
    status text not null,
    execution_mode text not null default 'dry_run',
    requires_approval boolean not null default false,
    approved boolean not null default false,
    started_at timestamptz not null,
    updated_at timestamptz not null,
    finished_at timestamptz null,
    result jsonb null,
    error text not null default '',
    logs jsonb not null default '[]'::jsonb
);

create index if not exists integration_runs_started_at_idx
    on public.integration_runs (started_at desc);

create index if not exists integration_runs_task_id_idx
    on public.integration_runs (task_id);
