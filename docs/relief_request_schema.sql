-- Draft schema for monetization relief backoffice

create table relief_requests (
    request_id text primary key,
    requester_channel_name text not null,
    requester_email text not null,
    requester_notes text not null default '',
    status text not null,
    submitted_via text not null default 'web',
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create table relief_request_items (
    request_id text not null references relief_requests(request_id) on delete cascade,
    work_id text not null,
    work_title text not null,
    rights_holder_name text not null,
    channel_folder_name text not null default '',
    primary key (request_id, work_id)
);

create table rights_holder_contacts (
    holder_id text primary key,
    holder_name text not null,
    recipient_email text not null,
    template_key text not null default 'rights_holder_request'
);

create table rights_holder_contact_works (
    holder_id text not null references rights_holder_contacts(holder_id) on delete cascade,
    work_title text not null,
    primary key (holder_id, work_title)
);

create table mail_templates (
    template_key text primary key,
    subject_template text not null,
    body_template text not null,
    is_html boolean not null default true,
    updated_at timestamptz not null default now()
);

create table outbound_mails (
    mail_id text primary key,
    request_id text not null references relief_requests(request_id) on delete cascade,
    holder_name text not null,
    recipient_email text not null,
    subject text not null,
    body text not null,
    status text not null,
    sent_at timestamptz,
    error_message text not null default ''
);

create table inbound_mail_events (
    event_id text primary key,
    request_id text not null references relief_requests(request_id) on delete cascade,
    sender_email text not null,
    subject text not null,
    body_excerpt text not null default '',
    has_attachments boolean not null default false,
    received_at timestamptz not null
);

create table uploaded_documents (
    document_id text primary key,
    request_id text not null references relief_requests(request_id) on delete cascade,
    holder_name text not null,
    drive_file_id text not null,
    drive_file_url text not null,
    stored_path text not null,
    uploaded_at timestamptz not null
);

create table relief_audit_logs (
    audit_id bigserial primary key,
    request_id text not null references relief_requests(request_id) on delete cascade,
    action text not null,
    actor text not null,
    payload_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
