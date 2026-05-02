const TABS = [
  { id: "ops_admin", label: "운영지원 어드민", icon: "🛠️" },
  { id: "homepage_auto", label: "홈페이지를 통한 자동화", icon: "🌐" },
  { id: "channels", label: "내 채널", icon: "🎞️" },
  { id: "b2_analytics", label: "B-2 분석", icon: "📊" },
  { id: "runs", label: "실행 기록", icon: "🧾" },
  { id: "resources", label: "환경 요약", icon: "🧩" },
];

const TAB_SUBTITLE = {
  ops_admin: "운영자가 직접 실행하고 점검하는 자동화 도구입니다.",
  homepage_auto: "홈페이지에서 인입된 요청을 처리하는 자동화 도구입니다.",
  channels: "내 채널에서 이용 가능한 영상 목록을 확인하고 관련 업무를 요청합니다.",
  b2_analytics: "저장된 네이버 클립 성과 데이터를 기간/채널/클립/작품/권리사 기준으로 탐색합니다.",
  runs: "최근 자동화 실행 결과와 상태를 확인합니다.",
  resources: "현재 대시보드가 참조하는 주요 자원과 연결 상태입니다.",
};

const CHANNEL_ACTION_LABELS = {
  "work-approval": "작품사용신청 승인",
  coupon: "쿠폰 신청",
  relief: "저작권 소명 신청",
};

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
  b2Options: null,
  b2Analytics: null,
  b2LookerResult: null,
  b2Loading: false,
  b2Error: "",
  b2Filters: {
    checked_from: "",
    checked_to: "",
    uploaded_from: "",
    uploaded_to: "",
    channel_name: "",
    clip_title: "",
    work_title: "",
    rights_holder_name: "",
    platform: "",
    group_by: "clip",
    limit: 100,
  },
};

class IntegrationRepo {
  constructor(base = ".") {
    this.base = base;
  }
  async listTasks() {
    return (await fetch(`${this.base}/api/integration/tasks`)).json();
  }
  async listRuns() {
    return (await fetch(`${this.base}/api/integration/runs`)).json();
  }
  async loadResources() {
    return (await fetch(`${this.base}/api/integration/resources`)).json();
  }
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
  constructor(base = ".") {
    this.base = base;
  }
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

class B2Repo {
  constructor(base = ".") {
    this.base = base;
  }
  async getOptions() {
    const res = await fetch(`${this.base}/api/b2/analytics/options`);
    if (!res.ok) throw new Error(`B-2 옵션 로드 실패 (${res.status})`);
    return res.json();
  }
  async getAnalytics(params) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) {
        query.set(key, String(value));
      }
    });
    const res = await fetch(`${this.base}/api/b2/analytics?${query.toString()}`);
    if (!res.ok) throw new Error(`B-2 데이터 조회 실패 (${res.status})`);
    return res.json();
  }
  async generateLooker(payload) {
    const res = await fetch(`${this.base}/api/b2/looker-studio/generate-send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Looker Studio 요청 실패 (${res.status})`);
    }
    return res.json();
  }
}

const integrationRepo = new IntegrationRepo(".");
const channelRepo = new ChannelRepo(".");
const b2Repo = new B2Repo(".");

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function chip(label, variant = "") {
  return `<span class="chip${variant ? ` chip--${variant}` : ""}">${esc(label)}</span>`;
}

function badge(taskId) {
  const cat = taskId.split("-")[0];
  return `<span class="task-badge task-badge--${cat.toLowerCase()}">${esc(taskId)}</span>`;
}

function findLatestRun(taskId) {
  return state.runs.find((run) => run.task_id === taskId) || null;
}

function optionList(values, selected) {
  return [`<option value="">전체</option>`]
    .concat(
      (values || []).map(
        (value) =>
          `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(value)}</option>`,
      ),
    )
    .join("");
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set("tab", state.activeTab);
  if (state.activeTab === "b2_analytics") {
    Object.entries(state.b2Filters).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) {
        params.set(`b2_${key}`, String(value));
      }
    });
  }
  const query = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

function hydrateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const tab = params.get("tab");
  if (tab && TABS.some((item) => item.id === tab)) {
    state.activeTab = tab;
  }
  Object.keys(state.b2Filters).forEach((key) => {
    const value = params.get(`b2_${key}`);
    if (value !== null) {
      state.b2Filters[key] = key === "limit" ? Number(value) : value;
    }
  });
}

function renderTabs() {
  return `<nav class="tabs" role="tablist">
    ${TABS.map(
      (tab) => `
      <button class="tab-btn${state.activeTab === tab.id ? " active" : ""}"
        data-tab="${tab.id}" type="button" role="tab"
        aria-selected="${state.activeTab === tab.id}">
        <span class="tab-icon">${tab.icon}</span>
        <span>${esc(tab.label)}</span>
      </button>`,
    ).join("")}
  </nav>`;
}

function renderTaskCard(task) {
  const related = Object.entries(task.sheet_links || {}).filter(([key, value]) => key !== "로그시트" && value);
  const logLink = task.sheet_links?.["로그시트"] || "";
  const cat = task.task_id.split("-")[0].toLowerCase();
  const latestRun = findLatestRun(task.task_id);
  const latestBody = latestRun?.result?.body || latestRun?.result || {};
  const timing =
    task.task_id === "B-2" && (latestBody.crawl_seconds !== undefined || latestBody.elapsed_seconds !== undefined)
      ? `<div class="chip-row">
          ${latestBody.crawl_seconds !== undefined ? chip(`crawl_seconds: ${latestBody.crawl_seconds}s`, "succeeded") : ""}
          ${latestBody.elapsed_seconds !== undefined ? chip(`elapsed_seconds: ${latestBody.elapsed_seconds}s`, "succeeded") : ""}
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
        ${(task.targets || []).map((target) => chip(target)).join("")}
        ${chip(`트리거: ${task.trigger_mode}`)}
        ${task.requires_approval ? chip("승인 필요", "warn") : ""}
        ${latestRun ? chip(`최근 실행: ${latestRun.status}`, latestRun.status) : ""}
      </div>
      ${timing}
      ${related.length ? `
        <div class="link-row">
          <span class="link-row__label">관련 시트</span>
          <div class="link-row__links">
            ${related.map(([name, url]) => `<a class="pill-link" href="${esc(url)}" target="_blank" rel="noopener">${esc(name)}</a>`).join("")}
            ${logLink ? `<a class="pill-link pill-link--muted" href="${esc(logLink)}" target="_blank" rel="noopener">로그</a>` : ""}
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
          <button class="btn btn--ghost run-btn" type="button" data-task-id="${esc(task.task_id)}" data-mode="dry_run">Dry Run</button>
          <button class="btn run-btn" type="button" data-task-id="${esc(task.task_id)}" data-mode="real_run">Real Run</button>
        </div>
      </div>
    </div>
  </article>`;
}

function renderToolsPanel(tabId) {
  const filtered = state.tasks.filter((task) => (task.tab_group || "ops_admin") === tabId);
  return `
  <section class="panel">
    <p class="panel-subtitle">${esc(TAB_SUBTITLE[tabId] || "")}</p>
    <div class="task-grid">
      ${filtered.length ? filtered.map(renderTaskCard).join("") : `<div class="empty">등록된 도구가 없습니다.</div>`}
    </div>
  </section>`;
}

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
        <button class="btn channel-action-btn" type="button" data-action-type="work-approval" data-video-id="${esc(video.video_id)}">작품사용신청 승인</button>
        <button class="btn btn--ghost channel-action-btn" type="button" data-action-type="coupon" data-video-id="${esc(video.video_id)}">쿠폰 신청</button>
        <button class="btn btn--soft channel-action-btn" type="button" data-action-type="relief" data-video-id="${esc(video.video_id)}">저작권 소명 신청</button>
      </div>
    </div>
  </article>`;
}

function renderChannelPanel() {
  let content = `<div class="empty">이용 가능한 영상이 없습니다.</div>`;
  if (state.channelLoading) {
    content = `<div class="empty loading-pulse">영상 목록을 불러오는 중입니다.</div>`;
  } else if (state.channelError) {
    content = `<div class="infobox infobox--danger">${esc(state.channelError)}</div>`;
  } else if (state.channelVideos.length) {
    content = state.channelVideos.map(renderVideoCard).join("");
  }

  return `
  <section class="panel">
    <p class="panel-subtitle">${esc(TAB_SUBTITLE.channels)}</p>
    <div class="panel-toolbar">
      <span class="chip">영상 수 ${state.channelVideos.length}</span>
      <button id="refresh-videos" class="btn btn--ghost" type="button">새로고침</button>
    </div>
    <div class="video-grid">${content}</div>
  </section>`;
}

function renderRunsPanel() {
  return `
  <section class="panel">
    <p class="panel-subtitle">${esc(TAB_SUBTITLE.runs)}</p>
    <div class="task-grid">
      ${state.runs.length ? state.runs.map((run) => `
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

function renderResourcesPanel() {
  const tasks = state.resources?.tasks || [];
  return `
  <section class="panel">
    <p class="panel-subtitle">${esc(TAB_SUBTITLE.resources)}</p>
    <div class="resource-card"><pre>${esc(JSON.stringify(state.resources || {}, null, 2))}</pre></div>
    <div class="task-grid" style="margin-top:14px">
      ${tasks.map((task) => `
        <article class="resource-card">
          <h3>${esc(task.title)}</h3>
          <div class="chip-row">
            ${chip(task.task_id)}
            ${chip(task.supports_dry_run ? "Dry Run 지원" : "Dry Run 미지원")}
          </div>
        </article>`).join("")}
    </div>
  </section>`;
}

function renderB2Summary(summary = {}) {
  const cards = [
    ["클립 수", summary.clip_count ?? 0],
    ["채널 수", summary.channel_count ?? 0],
    ["작품 수", summary.work_count ?? 0],
    ["권리사 수", summary.rights_holder_count ?? 0],
    ["총 조회수", Number(summary.total_views ?? 0).toLocaleString("ko-KR")],
    ["최고 조회수", Number(summary.max_views ?? 0).toLocaleString("ko-KR")],
  ];
  return cards.map(([label, value]) => `
    <article class="metric-card">
      <div class="metric-label">${esc(label)}</div>
      <div class="metric-value">${esc(value)}</div>
    </article>`).join("");
}

function renderB2GroupTable(groups = []) {
  if (!groups.length) {
    return `<div class="empty">조건에 맞는 집계 데이터가 없습니다.</div>`;
  }
  return `
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>그룹</th>
          <th>클립 수</th>
          <th>채널 수</th>
          <th>작품 수</th>
          <th>권리사 수</th>
          <th>총 조회수</th>
          <th>최종 데이터확인일</th>
        </tr>
      </thead>
      <tbody>
        ${groups.map((item) => `
          <tr>
            <td>${esc(item.group_key)}</td>
            <td>${esc(item.clip_count)}</td>
            <td>${esc(item.channel_count)}</td>
            <td>${esc(item.work_count)}</td>
            <td>${esc(item.rights_holder_count)}</td>
            <td>${Number(item.total_views || 0).toLocaleString("ko-KR")}</td>
            <td>${esc(item.latest_checked_at || "")}</td>
          </tr>`).join("")}
      </tbody>
    </table>
  </div>`;
}

function renderB2RowsTable(rows = []) {
  if (!rows.length) {
    return `<div class="empty">조건에 맞는 클립 데이터가 없습니다.</div>`;
  }
  return `
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>영상URL</th>
          <th>영상업로드일</th>
          <th>채널명</th>
          <th>조회수</th>
          <th>데이터확인일</th>
          <th>제목</th>
          <th>작품</th>
          <th>플랫폼</th>
          <th>권리사</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.video_url ? `<a href="${esc(row.video_url)}" target="_blank" rel="noopener">열기</a>` : ""}</td>
            <td>${esc(row.uploaded_at || "")}</td>
            <td>${esc(row.channel_name || "")}</td>
            <td>${Number(row.view_count || 0).toLocaleString("ko-KR")}</td>
            <td>${esc(row.checked_at || "")}</td>
            <td>${esc(row.clip_title || "")}</td>
            <td>${esc(row.work_title || "")}</td>
            <td>${esc(row.platform || "")}</td>
            <td>${esc(row.rights_holder_name || "")}</td>
          </tr>`).join("")}
      </tbody>
    </table>
  </div>`;
}

function renderB2Panel() {
  const options = state.b2Options || {};
  const analytics = state.b2Analytics || {};
  const loading = state.b2Loading ? `<div class="infobox infobox--warn">B-2 데이터를 불러오는 중입니다.</div>` : "";
  const error = state.b2Error ? `<div class="infobox infobox--danger">${esc(state.b2Error)}</div>` : "";
  return `
  <section class="panel">
    <p class="panel-subtitle">${esc(TAB_SUBTITLE.b2_analytics)}</p>
    ${loading}
    ${error}
    <div class="b2-grid">
      <div class="b2-filters">
        <div class="field"><label>데이터확인일 시작</label><input id="b2_checked_from" type="date" value="${esc(state.b2Filters.checked_from)}" /></div>
        <div class="field"><label>데이터확인일 종료</label><input id="b2_checked_to" type="date" value="${esc(state.b2Filters.checked_to)}" /></div>
        <div class="field"><label>영상업로드일 시작</label><input id="b2_uploaded_from" type="date" value="${esc(state.b2Filters.uploaded_from)}" /></div>
        <div class="field"><label>영상업로드일 종료</label><input id="b2_uploaded_to" type="date" value="${esc(state.b2Filters.uploaded_to)}" /></div>
        <div class="field"><label>권리사</label><select id="b2_rights_holder_name">${optionList(options.rights_holder_names, state.b2Filters.rights_holder_name)}</select></div>
        <div class="field"><label>작품</label><select id="b2_work_title">${optionList(options.work_titles, state.b2Filters.work_title)}</select></div>
        <div class="field"><label>채널명</label><select id="b2_channel_name">${optionList(options.channel_names, state.b2Filters.channel_name)}</select></div>
        <div class="field"><label>플랫폼</label><select id="b2_platform">${optionList(options.platforms, state.b2Filters.platform)}</select></div>
        <div class="field"><label>클립 제목 검색</label><input id="b2_clip_title" type="text" value="${esc(state.b2Filters.clip_title)}" placeholder="부분 검색" /></div>
        <div class="field"><label>집계 기준</label>
          <select id="b2_group_by">
            <option value="clip"${state.b2Filters.group_by === "clip" ? " selected" : ""}>클립별</option>
            <option value="channel"${state.b2Filters.group_by === "channel" ? " selected" : ""}>채널별</option>
            <option value="work"${state.b2Filters.group_by === "work" ? " selected" : ""}>작품별</option>
            <option value="rights_holder"${state.b2Filters.group_by === "rights_holder" ? " selected" : ""}>권리사별</option>
          </select>
        </div>
        <div class="field"><label>표시 건수</label><input id="b2_limit" type="number" min="20" max="1000" step="20" value="${esc(state.b2Filters.limit)}" /></div>
      </div>
      <div class="button-row">
        <button id="b2_apply" class="btn" type="button">조회하기</button>
        <button id="b2_reset" class="btn btn--ghost" type="button">필터 초기화</button>
        <button id="b2_looker" class="btn btn--soft" type="button">Looker Studio 생성 및 담당자에게 보내기</button>
      </div>
      <div class="chip-row">
        ${options.checked_date_min ? chip(`checked_at ${options.checked_date_min} ~ ${options.checked_date_max}`) : ""}
        ${options.uploaded_date_min ? chip(`uploaded_at ${options.uploaded_date_min} ~ ${options.uploaded_date_max}`) : ""}
      </div>
      <div class="b2-metrics">${renderB2Summary(analytics.summary)}</div>
      <div class="table-card">
        <div class="table-toolbar">
          <div>
            <h2 class="panel-h2">집계 결과</h2>
            <p class="panel-subtitle">권리사별 Looker Studio 생성 전에 범위를 검토할 수 있습니다.</p>
          </div>
          <div class="chip-row">
            ${chip(`group_by: ${state.b2Filters.group_by}`)}
            ${chip(`rows: ${analytics.rows?.length || 0}`)}
            ${chip(`groups: ${analytics.groups?.length || 0}`)}
          </div>
        </div>
        ${renderB2GroupTable(analytics.groups || [])}
      </div>
      <div class="table-card">
        <div class="table-toolbar">
          <div>
            <h2 class="panel-h2">클립 상세</h2>
            <p class="panel-subtitle">Looker Studio와 어드민 조회가 함께 참조하는 원본 데이터입니다.</p>
          </div>
        </div>
        ${renderB2RowsTable(analytics.rows || [])}
      </div>
    </div>
  </section>`;
}

function renderDetailPanel() {
  if (state.activeTab === "b2_analytics") {
    return `
    <section class="panel">
      <h2 class="panel-h2">B-2 Looker Studio 액션</h2>
      <div class="infobox infobox--warn">실제 Looker Studio 생성 API는 아직 없어서 현재는 권리사별 payload와 발송 대상만 검토하는 stub입니다.</div>
      <pre class="result-pre">${esc(JSON.stringify(state.b2LookerResult || { status: "대기중" }, null, 2))}</pre>
    </section>`;
  }
  if (!state.selectedRun) {
    return `<section class="panel"><h2 class="panel-h2">선택한 실행</h2><div class="empty">좌측에서 작업을 실행하거나 실행 기록을 클릭하면 결과가 표시됩니다.</div></section>`;
  }
  const selectedBody = state.selectedRun?.result?.body || state.selectedRun?.result || {};
  return `
  <section class="panel">
    <h2 class="panel-h2">선택한 실행</h2>
    <div class="chip-row">
      ${chip(state.selectedRun.title || "")}
      ${chip(state.selectedRun.status || "", state.selectedRun.status)}
      ${chip(`모드: ${state.selectedRun.execution_mode || ""}`)}
      ${selectedBody.crawl_seconds !== undefined ? chip(`crawl_seconds: ${selectedBody.crawl_seconds}s`, "succeeded") : ""}
      ${selectedBody.elapsed_seconds !== undefined ? chip(`elapsed_seconds: ${selectedBody.elapsed_seconds}s`, "succeeded") : ""}
    </div>
    <pre class="result-pre">${esc(JSON.stringify(state.selectedRun, null, 2))}</pre>
  </section>`;
}

function renderActionPanel() {
  return `
  <section class="panel">
    <h2 class="panel-h2">채널 액션 결과</h2>
    ${state.channelActionLog
      ? `<pre class="result-pre">${esc(JSON.stringify(state.channelActionLog, null, 2))}</pre>`
      : `<div class="empty">내 채널 탭에서 버튼을 누르면 결과가 이곳에 표시됩니다.</div>`}
  </section>`;
}

function renderLeft() {
  switch (state.activeTab) {
    case "ops_admin":
      return renderToolsPanel("ops_admin");
    case "homepage_auto":
      return renderToolsPanel("homepage_auto");
    case "channels":
      return renderChannelPanel();
    case "b2_analytics":
      return renderB2Panel();
    case "runs":
      return renderRunsPanel();
    case "resources":
      return renderResourcesPanel();
    default:
      return renderToolsPanel("ops_admin");
  }
}

function render() {
  const root = document.getElementById("app");
  root.innerHTML = `
    <header class="hero">
      <div class="hero__text">
        <h1 class="hero__title">Rhoonart 운영 대시보드</h1>
        <p class="hero__sub">자동화 도구 실행, 관련 시트 확인, 채널 영상 요청, B-2 성과 분석을 한 화면에서 관리합니다.</p>
      </div>
    </header>
    ${renderTabs()}
    <div class="layout">
      <div class="stack">${renderLeft()}</div>
      <div class="stack">
        ${renderDetailPanel()}
        ${state.activeTab === "b2_analytics" ? "" : renderActionPanel()}
      </div>
    </div>`;
  bindEvents();
}

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

function buildMockActionResponse(actionType, video) {
  if (actionType === "work-approval") {
    return {
      status: "mocked",
      action_type: "work-approval",
      task_id: "A-2",
      payload: { channel_name: video.channel_name, work_title: video.title, dry_run: true },
      summary: `${video.channel_name} 채널의 '${video.title}' 작품사용신청 승인 mock`,
    };
  }
  if (actionType === "coupon") {
    return {
      status: "mocked",
      action_type: "coupon",
      task_id: "C-4",
      payload: { source: "channel_dashboard", creator_name: video.channel_name, text: `${video.title} 쿠폰 요청` },
      summary: `${video.title} 쿠폰 C-4 연결`,
    };
  }
  return {
    status: "mocked",
    action_type: "relief",
    task_id: "D-2",
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

async function handleChannelAction(actionType, videoId) {
  const video = state.channelVideos.find((item) => item.video_id === videoId);
  if (!video) return;

  let mockResponse;
  try {
    mockResponse = await channelRepo.requestAction(actionType, video);
  } catch {
    mockResponse = buildMockActionResponse(actionType, video);
  }

  let automationRun = null;
  if (mockResponse?.task_id && mockResponse?.payload) {
    automationRun = await integrationRepo.startRun(mockResponse.task_id, mockResponse.payload, "dry_run", false);
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

async function loadChannelVideos() {
  state.channelLoading = true;
  state.channelError = "";
  render();
  try {
    state.channelVideos = await channelRepo.listVideos();
  } catch (error) {
    state.channelVideos = [];
    state.channelError = error.message || String(error);
  } finally {
    state.channelLoading = false;
    render();
  }
}

function readB2FiltersFromDom() {
  state.b2Filters.checked_from = document.getElementById("b2_checked_from")?.value || "";
  state.b2Filters.checked_to = document.getElementById("b2_checked_to")?.value || "";
  state.b2Filters.uploaded_from = document.getElementById("b2_uploaded_from")?.value || "";
  state.b2Filters.uploaded_to = document.getElementById("b2_uploaded_to")?.value || "";
  state.b2Filters.channel_name = document.getElementById("b2_channel_name")?.value || "";
  state.b2Filters.clip_title = document.getElementById("b2_clip_title")?.value.trim() || "";
  state.b2Filters.work_title = document.getElementById("b2_work_title")?.value || "";
  state.b2Filters.rights_holder_name = document.getElementById("b2_rights_holder_name")?.value || "";
  state.b2Filters.platform = document.getElementById("b2_platform")?.value || "";
  state.b2Filters.group_by = document.getElementById("b2_group_by")?.value || "clip";
  state.b2Filters.limit = Number(document.getElementById("b2_limit")?.value || 100);
}

async function loadB2Options() {
  state.b2Options = await b2Repo.getOptions();
  if (!state.b2Filters.checked_from && state.b2Options.checked_date_min) {
    state.b2Filters.checked_from = state.b2Options.checked_date_min;
  }
  if (!state.b2Filters.checked_to && state.b2Options.checked_date_max) {
    state.b2Filters.checked_to = state.b2Options.checked_date_max;
  }
}

async function loadB2Analytics() {
  state.b2Loading = true;
  state.b2Error = "";
  updateUrl();
  render();
  try {
    state.b2Analytics = await b2Repo.getAnalytics(state.b2Filters);
  } catch (error) {
    state.b2Analytics = null;
    state.b2Error = error.message || String(error);
  } finally {
    state.b2Loading = false;
    updateUrl();
    render();
  }
}

function resetB2Filters() {
  state.b2Filters = {
    checked_from: state.b2Options?.checked_date_min || "",
    checked_to: state.b2Options?.checked_date_max || "",
    uploaded_from: "",
    uploaded_to: "",
    channel_name: "",
    clip_title: "",
    work_title: "",
    rights_holder_name: "",
    platform: "",
    group_by: "clip",
    limit: 100,
  };
}

async function triggerB2Looker() {
  readB2FiltersFromDom();
  try {
    state.b2LookerResult = await b2Repo.generateLooker(state.b2Filters);
    updateUrl();
    render();
  } catch (error) {
    state.b2LookerResult = { status: "error", detail: error.message || String(error) };
    render();
  }
}

function bindEvents() {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      const nextTab = button.dataset.tab;
      if (state.activeTab === nextTab) return;
      state.activeTab = nextTab;
      updateUrl();
      render();
      if (nextTab === "channels" && !state.channelVideos.length && !state.channelLoading) {
        await loadChannelVideos();
      }
      if (nextTab === "b2_analytics" && !state.b2Options) {
        try {
          await loadB2Options();
          await loadB2Analytics();
        } catch (error) {
          state.b2Error = error.message || String(error);
          render();
        }
      }
    });
  });

  document.querySelectorAll(".run-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const taskId = button.dataset.taskId;
      const mode = button.dataset.mode;
      const approved = !!document.querySelector(`.approval-check[data-task-id="${taskId}"]`)?.checked;
      try {
        await runTask(taskId, mode, approved);
      } catch (error) {
        state.selectedRun = { title: taskId, status: "failed", error: error.message || String(error) };
        render();
      }
    });
  });

  document.querySelectorAll(".run-card").forEach((card) => {
    card.addEventListener("click", () => {
      const runId = card.dataset.runId;
      const run = state.runs.find((item) => item.run_id === runId);
      if (run) {
        state.selectedRun = run;
        render();
      }
    });
  });

  document.querySelectorAll(".channel-action-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      await handleChannelAction(button.dataset.actionType, button.dataset.videoId);
    });
  });

  const refreshVideos = document.getElementById("refresh-videos");
  if (refreshVideos) {
    refreshVideos.addEventListener("click", async () => {
      await loadChannelVideos();
    });
  }

  const b2Apply = document.getElementById("b2_apply");
  if (b2Apply) {
    b2Apply.addEventListener("click", async () => {
      readB2FiltersFromDom();
      await loadB2Analytics();
    });
  }
  const b2Reset = document.getElementById("b2_reset");
  if (b2Reset) {
    b2Reset.addEventListener("click", async () => {
      resetB2Filters();
      await loadB2Analytics();
    });
  }
  const b2Looker = document.getElementById("b2_looker");
  if (b2Looker) {
    b2Looker.addEventListener("click", async () => {
      await triggerB2Looker();
    });
  }
}

async function bootstrap() {
  hydrateFromUrl();
  state.tasks = await integrationRepo.listTasks();
  state.runs = await integrationRepo.listRuns();
  state.resources = await integrationRepo.loadResources();
  if (state.activeTab === "channels") {
    await loadChannelVideos();
  }
  if (state.activeTab === "b2_analytics") {
    await loadB2Options();
    await loadB2Analytics();
  } else {
    render();
  }
  updateUrl();
}

bootstrap().catch((error) => {
  document.getElementById("app").innerHTML = `<div class="app-shell"><div class="infobox infobox--danger">대시보드 로딩 실패: ${esc(error.message || error)}</div></div>`;
});
