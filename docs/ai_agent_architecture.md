# AI Agent Introduction Architecture

## Scope

This document describes how the current automation modules can evolve from button-triggered workflows into AI-agent-driven operations.

Target tasks:

- A-2
- A-3
- B-2
- C-1
- C-2
- C-3
- C-4
- D-2
- D-3

## 1. Input Gateway

The future agent should not depend on a single UI trigger. Instead, all inbound events should enter through a normalized Input Gateway.

### Supported trigger types

- Browser dashboard button click
- Slack message received
- Email received
- Scheduled cron trigger
- Web form submission
- Google Sheets row change
- Admin API webhook

### Gateway responsibility

- parse raw event
- classify intent
- attach metadata
- enforce authentication and source validation
- create a normalized task envelope

### Normalized envelope

```json
{
  "source_type": "slack",
  "source_id": "channel-or-thread-id",
  "received_at": "2026-04-27T10:00:00Z",
  "intent": "approve_work_request",
  "payload": {},
  "requires_human_review": false,
  "trace_id": "trace-123"
}
```

This is the right place to handle unstructured inputs such as:

- email body analysis
- Slack free-text requests
- pasted admin notes

That means the Input Gateway becomes the first AI-assisted interpretation layer when raw text is ambiguous.

## 2. Agent Runtime

The agent layer should sit above the existing handlers, not replace them.

### Principle

- AI decides what to do
- deterministic modules do the actual business operation

### ReAct-style loop

1. Observe
   - read task envelope
   - gather prior context and recent run history
2. Think
   - determine probable business intent
   - identify missing data
   - decide whether approval is required
3. Act
   - select one or more tools
   - execute the existing automation module
4. Reflect
   - inspect result
   - decide next step, retry, escalate, or finish

### Tool layer

The current handlers become callable tools:

- `run_a2_work_approval`
- `run_a3_naver_clip_monthly`
- `run_b2_weekly_report`
- `run_c1_lead_filter`
- `run_c2_cold_email`
- `run_c3_work_register`
- `run_c4_coupon_notification`
- `run_d2_relief_request`
- `run_d3_kakao_creator_onboarding`

The dashboard runner already moves in this direction by wrapping handler calls behind a registry.

## 3. Human-in-the-loop and Safeguards

Approval points should be explicit.

### Mandatory approval candidates

- C-2 outbound cold email send
- C-3 work registration against a real admin API
- D-2 rights-holder email send
- D-2 customer-facing forwarding
- any bulk update to Google Sheets
- any action that changes external permissions or sends messages externally

### Guardrails

- dry-run mode by default for newly added tools
- environment-based allowlist for production execution
- per-task approval policy
- audit log for every agent decision
- payload snapshot before execution
- retry budget and circuit breaker
- rollback or compensating-action notes where rollback is impossible

### Approval envelope example

```json
{
  "task_id": "C-2",
  "summary": "Send 5 cold emails to YouTube leads filtered by genre=drama",
  "risk_level": "high",
  "preview": {
    "targets": 5,
    "sample_recipient": "lead@example.com"
  }
}
```

## 4. Repository Pattern and Supabase Migration

The dashboard and future agent orchestration should depend on repository interfaces, not on Google Sheets directly.

### Current direction

- handler logic depends on repository abstractions in some modules
- dashboard run logging already uses repository abstraction
- D-2 service is already shaped for pluggable persistence

### Migration approach

1. keep handler signatures stable
2. swap repository implementations from Sheets to Supabase
3. preserve API contracts used by dashboard and agent
4. add a unified execution log table for agent traces and human approvals

### Suggested Supabase tables

- `integration_runs`
- `integration_run_logs`
- `agent_traces`
- `agent_approvals`
- `agent_tool_invocations`
- existing business tables such as `relief_requests`

## 5. Recommended Target Architecture

```text
Input Gateway
  -> Intent Classifier
  -> Policy / Approval Check
  -> Agent Orchestrator
  -> Tool Registry
  -> Existing Automation Modules
  -> Repository Layer
  -> Sheets / Supabase / Email / Slack / Drive
```

## 6. Practical Rollout Plan

### Phase 1

- browser dashboard
- shared task registry
- normalized run logs

### Phase 2

- structured Input Gateway
- Slack and email ingestion adapters
- approval UI

### Phase 3

- AI-based intent classification
- ReAct-style tool selection
- trace storage in Supabase

### Phase 4

- partial autonomy on low-risk tasks
- approval-required autonomy on high-risk tasks

## 7. Design Review Summary

- The safest path is to keep AI above the current deterministic automation modules.
- Input Gateway should own unstructured trigger interpretation.
- Human approval must gate any external send, permission change, or production write.
- Supabase should become the persistence layer for both business data and agent traces without requiring dashboard rewrites.
