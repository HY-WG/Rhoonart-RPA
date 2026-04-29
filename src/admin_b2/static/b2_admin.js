const api = {
  async getJson(url) {
    const res = await fetch(url);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const payload = await res.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  },
  async postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const payload = await res.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  },
};

const state = {
  options: null,
  result: null,
  loading: false,
  lookerResult: null,
  filters: {
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

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function optionList(values, selected) {
  return [`<option value="">전체</option>`]
    .concat((values || []).map((value) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(value)}</option>`))
    .join("");
}

function serializeFilters() {
  const params = new URLSearchParams();
  Object.entries(state.filters).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

function metricsMarkup(summary) {
  const cards = [
    ["클립 수", summary?.clip_count ?? 0],
    ["채널 수", summary?.channel_count ?? 0],
    ["작품 수", summary?.work_count ?? 0],
    ["권리사 수", summary?.rights_holder_count ?? 0],
    ["총 조회수", (summary?.total_views ?? 0).toLocaleString("ko-KR")],
    ["최고 조회수", (summary?.max_views ?? 0).toLocaleString("ko-KR")],
  ];
  return cards.map(([label, value]) => `
    <article class="metric-card">
      <div class="metric-label">${esc(label)}</div>
      <div class="metric-value">${esc(value)}</div>
    </article>
  `).join("");
}

function renderRowsTable(rows) {
  if (!rows?.length) {
    return `<div class="empty">조건에 맞는 데이터가 없습니다.</div>`;
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
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderGroupsTable(groups) {
  if (!groups?.length) {
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
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function render() {
  const app = document.getElementById("app");
  const options = state.options || {};
  const result = state.result || {};
  app.innerHTML = `
    <div class="shell">
      <section class="hero">
        <h1>B-2 네이버 클립 성과 어드민</h1>
        <p>
          Supabase에 저장된 클립 단위 데이터를 기준으로 기간별 조회와 채널/클립/작품/권리사 필터링을 수행합니다.
          같은 화면에서 권리사별 Looker Studio 생성 및 담당자 발송 요청도 준비할 수 있습니다.
        </p>
      </section>

      <div class="layout">
        <div class="stack">
          <section class="panel">
            <h2>필터</h2>
            <p class="panel-subtitle">데이터확인일과 영상업로드일을 각각 필터링할 수 있고, 그룹 기준도 바꿔서 집계할 수 있습니다.</p>
            <div class="filters">
              <div class="field">
                <label>데이터확인일 시작</label>
                <input id="checked_from" type="date" value="${esc(state.filters.checked_from)}" />
              </div>
              <div class="field">
                <label>데이터확인일 종료</label>
                <input id="checked_to" type="date" value="${esc(state.filters.checked_to)}" />
              </div>
              <div class="field">
                <label>영상업로드일 시작</label>
                <input id="uploaded_from" type="date" value="${esc(state.filters.uploaded_from)}" />
              </div>
              <div class="field">
                <label>영상업로드일 종료</label>
                <input id="uploaded_to" type="date" value="${esc(state.filters.uploaded_to)}" />
              </div>
              <div class="field">
                <label>권리사</label>
                <select id="rights_holder_name">${optionList(options.rights_holder_names, state.filters.rights_holder_name)}</select>
              </div>
              <div class="field">
                <label>작품</label>
                <select id="work_title">${optionList(options.work_titles, state.filters.work_title)}</select>
              </div>
              <div class="field">
                <label>채널명</label>
                <select id="channel_name">${optionList(options.channel_names, state.filters.channel_name)}</select>
              </div>
              <div class="field">
                <label>플랫폼</label>
                <select id="platform">${optionList(options.platforms, state.filters.platform)}</select>
              </div>
              <div class="field">
                <label>클립 제목 검색</label>
                <input id="clip_title" type="text" value="${esc(state.filters.clip_title)}" placeholder="부분 검색" />
              </div>
              <div class="field">
                <label>집계 기준</label>
                <select id="group_by">
                  <option value="clip"${state.filters.group_by === "clip" ? " selected" : ""}>클립별</option>
                  <option value="channel"${state.filters.group_by === "channel" ? " selected" : ""}>채널별</option>
                  <option value="work"${state.filters.group_by === "work" ? " selected" : ""}>작품별</option>
                  <option value="rights_holder"${state.filters.group_by === "rights_holder" ? " selected" : ""}>권리사별</option>
                </select>
              </div>
              <div class="field">
                <label>표시 건수</label>
                <input id="limit" type="number" min="20" max="1000" step="20" value="${esc(state.filters.limit)}" />
              </div>
            </div>
            <div class="button-row">
              <button id="applyFilters" class="btn">조회하기</button>
              <button id="resetFilters" class="btn secondary">필터 초기화</button>
              <button id="lookerAction" class="btn warn">Looker Studio 생성 및 담당자에게 보내기</button>
            </div>
          </section>

          <section class="panel">
            <h2>요약</h2>
            <p class="panel-subtitle">현재 조건으로 필터링된 데이터의 집계 요약입니다.</p>
            <div class="metrics">${metricsMarkup(result.summary)}</div>
          </section>

          <section class="table-card">
            <div class="table-toolbar">
              <div>
                <h2>집계 결과</h2>
                <p class="panel-subtitle">권리사별 Looker Studio 생성 대상 확인용입니다.</p>
              </div>
              <div class="chips">
                <span class="chip">group_by: ${esc(state.filters.group_by)}</span>
                <span class="chip ok">rows: ${esc(result.rows?.length || 0)}</span>
                <span class="chip">groups: ${esc(result.groups?.length || 0)}</span>
              </div>
            </div>
            ${renderGroupsTable(result.groups)}
          </section>

          <section class="table-card">
            <div class="table-toolbar">
              <div>
                <h2>클립 상세</h2>
                <p class="panel-subtitle">실제 저장된 clip-level rows입니다. Looker Studio와 어드민 조회의 공통 원본입니다.</p>
              </div>
            </div>
            ${renderRowsTable(result.rows)}
          </section>
        </div>

        <div class="stack">
          <section class="detail-card">
            <h2>필터 옵션 상태</h2>
            <div class="chips" style="margin-bottom: 12px;">
              <span class="chip">checked_at: ${esc(options.checked_date_min || "-")} ~ ${esc(options.checked_date_max || "-")}</span>
              <span class="chip">uploaded_at: ${esc(options.uploaded_date_min || "-")} ~ ${esc(options.uploaded_date_max || "-")}</span>
            </div>
            <pre>${esc(JSON.stringify(options, null, 2))}</pre>
          </section>

          <section class="detail-card">
            <h2>Looker Studio 액션</h2>
            <div class="status warn">
              실제 Looker Studio 생성 API는 아직 없어서 현재는 권리사별 payload와 발송 대상만 미리 검토하는 stub입니다.
            </div>
            <pre>${esc(JSON.stringify(state.lookerResult || { status: "대기중" }, null, 2))}</pre>
          </section>
        </div>
      </div>
    </div>
  `;

  document.getElementById("applyFilters").addEventListener("click", async () => {
    readFilters();
    await loadAnalytics();
  });
  document.getElementById("resetFilters").addEventListener("click", async () => {
    state.filters = {
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
    };
    await loadAnalytics();
  });
  document.getElementById("lookerAction").addEventListener("click", async () => {
    readFilters();
    try {
      state.lookerResult = await api.postJson("/api/admin/b2/looker-studio/generate-send", state.filters);
      render();
    } catch (error) {
      state.lookerResult = { status: "error", detail: String(error.message || error) };
      render();
    }
  });
}

function readFilters() {
  state.filters.checked_from = document.getElementById("checked_from").value;
  state.filters.checked_to = document.getElementById("checked_to").value;
  state.filters.uploaded_from = document.getElementById("uploaded_from").value;
  state.filters.uploaded_to = document.getElementById("uploaded_to").value;
  state.filters.channel_name = document.getElementById("channel_name").value;
  state.filters.clip_title = document.getElementById("clip_title").value.trim();
  state.filters.work_title = document.getElementById("work_title").value;
  state.filters.rights_holder_name = document.getElementById("rights_holder_name").value;
  state.filters.platform = document.getElementById("platform").value;
  state.filters.group_by = document.getElementById("group_by").value;
  state.filters.limit = Number(document.getElementById("limit").value || 100);
}

async function loadOptions() {
  state.options = await api.getJson("/api/admin/b2/analytics/options");
}

async function loadAnalytics() {
  const query = serializeFilters();
  state.result = await api.getJson(`/api/admin/b2/analytics?${query}`);
  render();
}

async function bootstrap() {
  await loadOptions();
  state.filters.checked_from = state.options.checked_date_min || "";
  state.filters.checked_to = state.options.checked_date_max || "";
  await loadAnalytics();
}

bootstrap().catch((error) => {
  document.getElementById("app").innerHTML = `<div class="shell"><div class="status warn">B-2 어드민 페이지 로딩 실패: ${esc(error.message || error)}</div></div>`;
});
