-- ============================================================
-- 001_agent_tables.sql
-- AI Agent 런타임 관련 테이블 (Supabase / PostgreSQL)
--
-- 적용:
--   supabase db push   또는
--   psql $DATABASE_URL -f migrations/001_agent_tables.sql
-- ============================================================

-- ------------------------------------------------------------
-- 1. agent_traces  — 에이전트 실행 이력
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_traces (
    trace_id        TEXT        PRIMARY KEY,
    task_id         TEXT        NOT NULL,
    envelope_id     TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'observing',
    steps           JSONB       NOT NULL DEFAULT '[]',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,

    CONSTRAINT agent_traces_status_check CHECK (
        status IN (
            'observing', 'thinking', 'awaiting_approval',
            'acting', 'reflecting', 'completed', 'failed'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_agent_traces_task_id
    ON agent_traces (task_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_traces_status
    ON agent_traces (status)
    WHERE status NOT IN ('completed', 'failed');

COMMENT ON TABLE  agent_traces           IS '에이전트 ReAct 루프 전체 실행 이력';
COMMENT ON COLUMN agent_traces.steps     IS 'TraceStep 배열 (JSON). 각 원소: step_num, state, thought, tool_name, tool_input, tool_output, error, timestamp';
COMMENT ON COLUMN agent_traces.status    IS 'AgentState enum 문자열 (마지막 상태)';


-- ------------------------------------------------------------
-- 2. agent_approvals  — 승인 요청 & 결과
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_approvals (
    approval_id     TEXT        PRIMARY KEY,
    trace_id        TEXT        NOT NULL REFERENCES agent_traces(trace_id) ON DELETE CASCADE,
    task_id         TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending',
    summary         TEXT        NOT NULL,
    risk_level      TEXT        NOT NULL,
    preview         JSONB       NOT NULL DEFAULT '{}',
    checkpoint      JSONB       NOT NULL DEFAULT '{}',
    execution_result JSONB,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at      TIMESTAMPTZ,
    decided_by      TEXT        NOT NULL DEFAULT '',
    decision_note   TEXT        NOT NULL DEFAULT '',

    CONSTRAINT agent_approvals_status_check CHECK (
        status IN ('pending', 'approved', 'rejected', 'executed', 'failed', 'expired')
    ),
    CONSTRAINT agent_approvals_risk_level_check CHECK (
        risk_level IN ('low', 'medium', 'high', 'critical')
    )
);

CREATE INDEX IF NOT EXISTS idx_agent_approvals_status
    ON agent_approvals (status, requested_at DESC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_agent_approvals_task_id
    ON agent_approvals (task_id, requested_at DESC);

COMMENT ON TABLE  agent_approvals              IS '고위험 도구 실행 전 인간 승인 요청 레코드';
COMMENT ON COLUMN agent_approvals.checkpoint   IS 'ApprovalQueue.resume에 필요한 에이전트 상태 전체 스냅샷';
COMMENT ON COLUMN agent_approvals.preview      IS '승인자에게 보여주는 실행 예정 파라미터';


-- ------------------------------------------------------------
-- 3. agent_tool_invocations  — 도구 호출 상세 로그
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_tool_invocations (
    invocation_id   BIGSERIAL   PRIMARY KEY,
    trace_id        TEXT        NOT NULL REFERENCES agent_traces(trace_id) ON DELETE CASCADE,
    step_num        INTEGER     NOT NULL,
    tool_name       TEXT        NOT NULL,
    tool_input      JSONB       NOT NULL DEFAULT '{}',
    tool_output     JSONB,
    error           TEXT,
    duration_ms     INTEGER,
    invoked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_tool_invocations_trace
    ON agent_tool_invocations (trace_id, step_num);

CREATE INDEX IF NOT EXISTS idx_agent_tool_invocations_tool
    ON agent_tool_invocations (tool_name, invoked_at DESC);

COMMENT ON TABLE agent_tool_invocations IS '에이전트 도구 호출 상세 기록 (감사 / 성능 분석용)';


-- ------------------------------------------------------------
-- 4. Row Level Security (RLS) — Supabase 전용
--    서비스 롤(service_role)만 접근 허용 (anon 차단)
-- ------------------------------------------------------------
ALTER TABLE agent_traces           ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_approvals        ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tool_invocations ENABLE ROW LEVEL SECURITY;

-- service_role 전체 허용 정책
CREATE POLICY "service_role_all_traces"
    ON agent_traces FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_approvals"
    ON agent_approvals FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_invocations"
    ON agent_tool_invocations FOR ALL TO service_role USING (true) WITH CHECK (true);
