# Company-Wide CLAUDE.md Attributes for Business RPA

Context and attributes to consider when building RPA for the business.

---

## 1. Project Overview

```markdown
## Project
- Business domain (HR, Finance, Supply Chain, etc.)
- Target systems/applications being automated (SAP, Salesforce, web portals, etc.)
- Automation type: UI-based, API-based, or hybrid
```

---

## 2. Environment & Infrastructure

```markdown
## Environment
- OS and version where bots run (Windows Server, etc.)
- Runtime: Python/UiPath/Automation Anywhere/Power Automate
- Browser versions (if web automation)
- Credential management: where secrets are stored (Vault, env vars, etc.)
- Orchestrator/scheduler in use
```

---

## 3. Automation Scope & Constraints

```markdown
## Automation Rules
- Which processes are in-scope vs. out-of-scope
- Steps that MUST have human-in-the-loop approval
- Retry logic standards (max retries, backoff)
- Timeout thresholds per step/process
- What to do on unhandled exceptions (halt, alert, fallback)
```

---

## 4. Data Handling

```markdown
## Data
- Input/output formats (Excel, CSV, DB tables, APIs)
- PII/sensitive data — masking or encryption requirements
- Data retention policy for bot logs and artifacts
- Audit trail requirements (regulatory context)
```

---

## 5. Error Handling & Alerting

```markdown
## Error Handling
- Escalation path when bot fails (email, Slack, ticket system)
- Log level standards (INFO, WARN, ERROR)
- Screenshot-on-failure policy
- Rollback steps for partial transactions
```

---

## 6. Security & Compliance

```markdown
## Security
- Do NOT hardcode credentials — always use vault/env
- MFA handling approach
- Audit log fields required per compliance standard (SOX, GDPR, etc.)
- Allowed/disallowed network targets
```

---

## 7. Testing Standards

```markdown
## Testing
- Unit test requirements for individual steps
- Regression test suite location
- Staging environment details (URLs, test accounts)
- How to mock external systems in tests
```

---

## 8. Code Style for Automation

```markdown
## Code Conventions
- Selector/locator strategy (prefer IDs over XPath, etc.)
- Naming convention for workflows/activities
- Modularization: one workflow per logical step
- Config file structure (not hardcoded values)
```

---

## Priority Reference Table

| Priority | Attribute | Why |
|---|---|---|
| High | Exception handling strategy | Bots fail silently without it |
| High | Credential/secrets approach | Security risk |
| High | Audit/logging requirements | Compliance and debugging |
| High | Human-in-the-loop triggers | Business process integrity |
| Medium | Retry/idempotency rules | Prevents duplicate transactions |
| Medium | Target system version locks | Selectors break on upgrades |

---

*Use this as a checklist when setting up CLAUDE.md for any RPA project across the company.*
