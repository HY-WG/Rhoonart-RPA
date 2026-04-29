// ── 탭 구성 ──────────────────────────────────────────────────────────────
const TABS = [
  { id: "ops_admin",     label: "운영지원 어드민",      icon: "⚙️" },
  { id: "homepage_auto", label: "홈페이지 자동화",       icon: "🌐" },
  { id: "channels",      label: "내 채널",               icon: "📺" },
  { id: "runs",          label: "실행 기록",              icon: "📋" },
  { id: "resources",     label: "환경 요약",              icon: "🔧" },
];

// 탭별 설명
const TAB_SUBTITLE = {
  ops_admin:     "운영 팀이 직접 실행·모니터링하는 자동화 도구입니다.",
  homepage_auto: "홈페이지(laeebly.io)를 통해 인입되는 크리에이터 요청을 자동 처리합니다.",
  channels:      "내 채널에서 이용 가능한 영상 목록을 확인하고 관련 업무를 신청합니다.",
  runs:          "최근 실행 상태와 결과를 확인합니다.",
  resources:     "현재 대시보드가 바라보는 주요 자원과 연결 상태입니다.",
};

const CHANNEL_ACTION_LABELS = {
  "work-approval": "작품사용신청 승인",   // → A-2
  coupon:          "쿠폰 신청",           // → C-4
  relief:          "저작권 소명 신청",    // → D-2
};

// ── 상태 ─────────────────────────────────────────────────────────────────
const state = {
  activeTab: "ops_admin",
  tasks: [],
  runs: [],
  resources: null,
  channelVideos: [],
  selectedRun: null,
  channelActionLog: null,
  channelLoading: false,
  channelError: "",
};

// ── API 레이어 ────────────────────────────────────────────────────────────
class IntegrationRepo {
  constructor(base = ".") { this.base = base; }
  async listTasks() { return (await fetch(`${this.base}/api/integration/tasks`)).json(); }
  async listRuns()  { return (await fetch(`${this.base}/api/integration/runs`)).json(); }
  async loadResources() { return (await fetch(`${this.base}/api/integration/resources`)).json(); }
  async startRun(taskId, payload, executionMode = "dry_run", approved = false) {
    const res = await fetch(`${this.base}/api/integration/tasks/${taskId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload, execution_mode: executionMode, approved }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `request failed (${res.status})`);
    }
    return res.json();
  }
}

class ChannelRepo {
  constructor(base = ".") { this.base = base; }
  async listVideos() {
    const res = await fetch(`${this.base}/api/channels/me/videos`);
    if (!res.ok) throw new Error(`영상 목록 로드 실패 (${res.status})`);
    return res.json();
  }
  async requestAction(actionType, video) {
    const res = await fetch(`${this.base}/api/channel-actions/${actionType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(video),
    });
    if (!res.ok) throw new Error(`액션 요청 실패 (${res.status})`);
    return res.json();
  }
}

const integrationRepo = new IntegrationRepo(".");
const channelRepo     = new ChannelRepo(".");

// ── 유틸 ─────────────────────────────────────────────────────────────────
function esc(v) {
  return String(v)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function chip(label, variant = "") {
  return `<span class="chip${variant ? ` chip--${variant}` : ""}">${esc(label)}</span>`;
}

function badge(taskId) {
  const cat = taskId.split("-")[0];  // A / B / C / D
  return `<span class="task-badge task-badge--${cat.toLowerCase()}">${esc(taskId)}</span>`;
}

function findLatestRun(taskId) {
  return state.runs.find(run => run.task_id === taskId) || null;
}

// ── 탭 렌더 ───────────────────────────────────────────────────────────────
function renderTabs() {
  return `<nav class="tabs" role="tablist">
    ${TABS.map(t => `
      <button class="tab-btn${state.activeTab === t.id ? " active" : ""}"
        data-tab="${t.id}" type="button" role="tab"
        aria-selected="${state.activeTab === t.id}">
        <span class="tab-icon">${t.icon}</span>
        <span>${esc(t.label)}</span>
      </button>`).join("")}
  </nav>`;
}

// ── 도구 카드 ─────────────────────────────────────────────────────────────
function renderTaskCard(task) {
  const related = Object.entries(task.sheet_links || {}).filter(([k, v]) => k !== "로그시트" && v);
  const logLink = task.sheet_links?.["로그시트"] || "";
  const cat = task.task_id.split("-")[0].toLowerCase();
  const latestRun = findLatestRun(task.task_id);
  const latestBody = latestRun?.result?.body || latestRun?.result || {};
  const b2Timing = task.task_id === "B-2" && (latestBody.crawl_seconds !== undefined || latestBody.elapsed_seconds !== undefined)
    ? `<div class="chip-row">
        ${latestBody.crawl_seconds !== undefined ? chip(`crawl_seconds: ${latestBody.crawl_seconds}s`, "success") : ""}
        ${latestBody.elapsed_seconds !== undefined ? chip(`elapsed_seconds: ${latestBody.elapsed_seconds}s`, "success") : ""}
      </div>`
    : "";

  return `
<article class="task-card" data-task-id="${esc(task.task_id)}">
  <div class="task-card__header task-card__header--${cat}">
    ${badge(task.task_id)}
    <h3 class="task-card__title">${esc(task.title.replace(/^[A-Z]-\d+\s+/, ""))}</h3>
  </div>
  <div class="task-card__body">
    <p class="task-card__desc">${esc(task.description)}</p>

    <div class="chip-row">
      ${(task.targets || []).map(t => chip(t)).join("")}
      ${chip(`트리거: ${task.trigger_mode}`)}
      ${task.requires_approval ? chip("승인 필요", "warn") : ""}
      ${latestRun ? chip(`최근 실행: ${latestRun.status}`, latestRun.status) : ""}
    </div>
    ${b2Timing}

    ${related.length ? `
    <div class="link-row">
      <span class="link-row__label">관련 시트</span>
      <div class="link-row__links">
        ${related.map(([n, u]) => `<a class="pill-link" href="${esc(u)}" target="_blank" rel="noopener">${esc(n)} ↗</a>`).join("")}
        ${logLink ? `<a class="pill-link pill-link--muted" href="${esc(logLink)}" target="_blank" rel="noopener">로그 ↗</a>` : ""}
      </div>
    </div>` : ""}

    ${task.real_run_warning ? `<div class="infobox infobox--warn">${esc(task.real_run_warning)}</div>` : ""}

    <textarea class="payload-editor" data-task-id="${esc(task.task_id)}">${esc(JSON.stringify(task.default_payload, null, 2))}</textarea>

    <div class="card-actions">
      <label class="approve-toggle">
        <input type="checkbox" class="approval-check" data-task-id="${esc(task.task_id)}" />
        실제 실행 승인
      </label>
      <div class="btn-group">
        <button class="btn btn--ghost run-btn" type="button"
          data-task-id="${esc(task.task_id)}" data-mode="dry_run">Dry Run</button>
        <button class="btn run-btn" type="button"
          data-task-id="${esc(task.task_id)}" data-mode="real_run">Real Run</button>
      </div>
    </div>
  </div>
</article>`;
}

// ── 탭별 도구 패널 ────────────────────────────────────────────────────────
function renderToolsPanel(tabId) {
  // tab_group 미설정 태스크는 기본값 "ops_admin"으로 처리
  const filtered = state.tasks.filter(t => (t.tab_group || "ops_admin") === tabId);
  const isEmpty  = state.tasks.length === 0;
  const emptyMsg = isEmpty
    ? "도구를 불러오는 중이거나 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요."
    : "등록된 도구가 없습니다.";
  return `
<section class="panel">
  <p class="panel-subtitle">${esc(TAB_SUBTITLE[tabId] || "")}</p>
  <div class="task-grid">
    ${filtered.length ? filtered.map(renderTaskCard).join("") : `<div class="empty">${emptyMsg}</div>`}
  </div>
</section>`;
}

// ── 내 채널 패널 ──────────────────────────────────────────────────────────
function renderVideoCard(video) {
  return `
<article class="video-card">
  <div class="video-card__thumb">${esc(video.thumbnail_emoji || video.title.slice(0, 1))}</div>
  <div class="video-card__info">
    <div class="video-card__top">
      <div>
        <h3 class="video-card__title">${esc(video.title)}</h3>
        <p class="video-card__desc">${esc(video.description)}</p>
      </div>
      <span class="status-dot status-dot--ok" title="이용 가능"></span>
    </div>
    <div class="chip-row">
      ${chip(video.channel_name)}
      ${chip(video.rights_holder_name)}
      ${chip(video.platform)}
    </div>
    <div class="video-card__actions">
      <button class="btn channel-action-btn" type="button"
        data-action-type="work-approval" data-video-id="${esc(video.video_id)}">작품사용신청 승인</button>
      <button class="btn btn--ghost channel-action-btn" type="button"
        data-action-type="coupon" data-video-id="${esc(video.video_id)}">쿠폰 신청</button>
      <button class="btn btn--soft channel-action-btn" type="button"
        data-action-type="relief" data-video-id="${esc(video.video_id)}">저작권 소명 신청</button>
    </div>
  </div>
</article>`;
}

function renderChannelPanel() {
  let content;
  if (state.channelLoading) {
    content = `<div class="empty loading-pulse">영상 목록을 불러오는 중...</div>`;
  } else if (state.channelError) {
    content = `<div class="infobox infobox--danger">${esc(state.channelError)}</div>`;
  } else if (!state.channelVideos.length) {
    content = `<div class="empty">이용 가능한 영상이 없습니다.</div>`;
  } else {
    content = state.channelVideos.map(renderVideoCard).join("");
  }

  return `
<section class="panel">
  <p class="panel-subtitle">${esc(TAB_SUBTITLE.channels)}</p>
  <div class="panel-toolbar">
    <span class="chip">${esc(`영상 수: ${state.channelVideos.length}`)}</span>
    <button id="refresh-videos" class="btn btn--ghost" type="button">새로고침</button>
  </div>
  <div class="video-grid">${content}</div>
</section>`;
}

// ── 실행 기록 패널 ────────────────────────────────────────────────────────
function renderRunsPanel() {
  return `
<section class="panel">
  <p class="panel-subtitle">${esc(TAB_SUBTITLE.runs)}</p>
  <div class="task-grid">
    ${state.runs.length ? state.runs.map(run => `
      <article class="run-card" data-run-id="${esc(run.run_id)}">
        <div class="run-card__head">
          <div>
            <h3>${esc(run.title)}</h3>
            <p class="text-muted small">${esc(run.run_id)}</p>
          </div>
          ${chip(run.status, run.status)}
        </div>
        <div class="chip-row">
          ${chip(`모드: ${run.execution_mode}`)}
          ${chip(new Date(run.started_at).toLocaleString("ko-KR"))}
        </div>
      </article>`).join("") : `<div class="empty">아직 실행 기록이 없습니다.</div>`}
  </div>
</section>`;
}

// ── 환경 요약 패널 ────────────────────────────────────────────────────────
function renderResourcesPanel() {
  const tasks = state.resources?.tasks || [];
  return `
<section class="panel">
  <p class="panel-subtitle">${esc(TAB_SUBTITLE.resources)}</p>
  <div class="resource-card"><pre>${esc(JSON.stringify(state.resources || {}, null, 2))}</pre></div>
  <div class="task-grid" style="margin-top:14px">
    ${tasks.map(t => `
      <article class="resource-card">
        <h3>${esc(t.title)}</h3>
        <div class="chip-row">
          ${chip(t.task_id)}
          ${chip(t.supports_dry_run ? "Dry Run 지원" : "Dry Run 미지원")}
        </div>
      </article>`).join("")}
  </div>
</section>`;
}

// ── 우측 패널 ─────────────────────────────────────────────────────────────
function renderDetailPanel() {
  if (!state.selectedRun) {
    return `<section class="panel"><h2 class="panel-h2">선택한 실행</h2>
      <div class="empty">좌측에서 작업을 실행하거나 실행 기록을 클릭하면 결과가 표시됩니다.</div>
    </section>`;
  }
  const selectedBody = state.selectedRun?.result?.body || state.selectedRun?.result || {};
  return `<section class="panel"><h2 class="panel-h2">선택한 실행</h2>
    <div class="chip-row">
      ${chip(state.selectedRun.title || "")}
      ${chip(state.selectedRun.status || "", state.selectedRun.status)}
      ${chip(`모드: ${state.selectedRun.execution_mode || ""}`)}
      ${selectedBody.crawl_seconds !== undefined ? chip(`crawl_seconds: ${selectedBody.crawl_seconds}s`, "success") : ""}
      ${selectedBody.elapsed_seconds !== undefined ? chip(`elapsed_seconds: ${selectedBody.elapsed_seconds}s`, "success") : ""}
    </div>
    <pre class="result-pre">${esc(JSON.stringify(state.selectedRun, null, 2))}</pre>
  </section>`;
}

function renderActionPanel() {
  return `<section class="panel"><h2 class="panel-h2">채널 액션 결과</h2>
    ${state.channelActionLog
      ? `<pre class="result-pre">${esc(JSON.stringify(state.channelActionLog, null, 2))}</pre>`
      : `<div class="empty">내 채널 탭에서 버튼을 누르면 결과가 여기 표시됩니다.</div>`}
  </section>`;
}

// ── 메인 렌더 ─────────────────────────────────────────────────────────────
function renderLeft() {
  switch (state.activeTab) {
    case "ops_admin":     return renderToolsPanel("ops_admin");
    case "homepage_auto": return renderToolsPanel("homepage_auto");
    case "channels":      return renderChannelPanel();
    case "runs":          return renderRunsPanel();
    case "resources":     return renderResourcesPanel();
    default:              return renderToolsPanel("ops_admin");
  }
}

function render() {
  const root = document.getElementById("app");
  root.innerHTML = `
    <header class="hero">
      <div class="hero__text">
        <h1 class="hero__title">Rhoonart 운영 대시보드</h1>
        <p class="hero__sub">자동화 도구 실행, 관련 시트 확인, 채널 영상 신청 흐름을 한 화면에서 관리합니다.</p>
      </div>
    </header>
    ${renderTabs()}
    <div class="layout">
      <div class="stack">${renderLeft()}</div>
      <div class="stack">
        ${renderDetailPanel()}
        ${renderActionPanel()}
      </div>
    </div>
  `;
  bindEvents();
}

// ── 이벤트 바인딩 ─────────────────────────────────────────────────────────
function parsePayload(taskId) {
  const ta = document.querySelector(`textarea[data-task-id="${taskId}"]`);
  if (!ta) throw new Error(`payload editor not found: ${taskId}`);
  return JSON.parse(ta.value);
}

async function runTask(taskId, mode, approved) {
  const payload = parsePayload(taskId);
  const run = await integrationRepo.startRun(taskId, payload, mode, approved);
  state.selectedRun = run;
  state.runs = await integrationRepo.listRuns();
  render();
}

async function handleChannelAction(actionType, videoId) {
  const video = state.channelVideos.find(v => v.video_id === videoId);
  if (!video) return;

  let mockResponse = null;
  let automationRun = null;

  // 백엔드 channel-action 엔드포인트가 없으면 인라인 mock 처리
  try {
    mockResponse = await channelRepo.requestAction(actionType, video);
  } catch {
    mockResponse = buildMockActionResponse(actionType, video);
  }

  if (mockResponse?.task_id && mockResponse?.payload) {
    automationRun = await integrationRepo.startRun(
      mockResponse.task_id, mockResponse.payload, "dry_run", false,
    );
    state.selectedRun = automationRun;
    state.runs = await integrationRepo.listRuns();
  }

  state.channelActionLog = {
    action_label: CHANNEL_ACTION_LABELS[actionType] || actionType,
    mock_response: mockResponse,
    automation_run: automationRun,
  };
  render();
}

function buildMockActionResponse(actionType, video) {
  if (actionType === "work-approval") {
    return {
      status: "mocked", action_type: "work-approval", task_id: "A-2",
      payload: { channel_name: video.channel_name, work_title: video.title, dry_run: true },
      summary: `${video.channel_name} 채널의 '${video.title}' 작품사용신청 승인 mock`,
    };
  }
  if (actionType === "coupon") {
    return {
      status: "mocked", action_type: "coupon", task_id: "C-4",
      payload: { source: "channel_dashboard", creator_name: video.channel_name, text: `${video.title} 쿠폰 신청` },
      summary: `${video.title} 쿠폰 C-4 연결`,
    };
  }
  return {
    status: "mocked", action_type: "relief", task_id: "D-2",
    payload: {
      requester_channel_name: video.channel_name,
      requester_email: video.contact_email,
      requester_notes: `${video.title} 저작권 소명 요청`,
      auto_send_mails: false,
      items: [{ work_id: video.video_id, work_title: video.title, rights_holder_name: video.rights_holder_name, channel_folder_name: video.channel_name }],
    },
    summary: `${video.title} 저작권 소명 D-2 연결`,
  };
}

function bindEvents() {
  // 탭 전환
  document.querySelectorAll("[data-tab]").forEach(btn => {
    btn.addEventListener("click", async () => {
      state.activeTab = btn.dataset.tab;
      if (state.activeTab === "channels" && !state.channelVideos.length) {
        await loadChannelVideos();
      }
      render();
    });
  });

  // 실행 버튼
  document.querySelectorAll(".run-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const taskId = btn.dataset.taskId;
        const mode   = btn.dataset.mode;
        const check  = document.querySelector(`.approval-check[data-task-id="${taskId}"]`);
        await runTask(taskId, mode, check?.checked || false);
      } catch (err) {
        state.selectedRun = { title: "실행 실패", status: "failed", error: String(err.message || err) };
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  // 실행 기록 클릭
  document.querySelectorAll(".run-card").forEach(card => {
    card.addEventListener("click", () => {
      const run = state.runs.find(r => r.run_id === card.dataset.runId);
      if (run) { state.selectedRun = run; render(); }
    });
  });

  // 채널 액션 버튼
  document.querySelectorAll(".channel-action-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await handleChannelAction(btn.dataset.actionType, btn.dataset.videoId);
      } catch (err) {
        state.channelActionLog = {
          action_label: CHANNEL_ACTION_LABELS[btn.dataset.actionType] || btn.dataset.actionType,
          error: String(err.message || err),
        };
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  // 영상 새로고침
  const refreshBtn = document.getElementById("refresh-videos");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.disabled = true;
      await loadChannelVideos();
      render();
      refreshBtn.disabled = false;
    });
  }
}

// ── 데이터 로드 ───────────────────────────────────────────────────────────
async function loadChannelVideos() {
  state.channelLoading = true;
  state.channelError = "";
  render();
  try {
    state.channelVideos = await channelRepo.listVideos();
  } catch (err) {
    state.channelError = String(err.message || err);
    state.channelVideos = [];
  } finally {
    state.channelLoading = false;
  }
}

async function boot() {
  // Promise.allSettled: 하나가 실패해도 나머지 데이터는 정상 표시
  const [tasksResult, resourcesResult, runsResult] = await Promise.allSettled([
    integrationRepo.listTasks(),
    integrationRepo.loadResources(),
    integrationRepo.listRuns(),
  ]);

  state.tasks     = tasksResult.status     === "fulfilled" ? tasksResult.value     : [];
  state.resources = resourcesResult.status === "fulfilled" ? resourcesResult.value : null;
  state.runs      = runsResult.status      === "fulfilled" ? runsResult.value      : [];

  if (tasksResult.status === "rejected") {
    console.error("[boot] 태스크 목록 로드 실패:", tasksResult.reason);
  }
  render();
}

boot().catch(err => {
  state.selectedRun = { title: "초기화 실패", status: "failed", error: String(err.message || err) };
  render();
});
