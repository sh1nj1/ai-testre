let tasks = [],
  selected = "",
  state = { scores: [], history: [] };
let serverOffset = 0;
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const drafts = new Map();
async function api(path, body) {
  const r = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const result = await r.json();
  if (!r.ok) throw new Error(result.error || "요청에 실패했습니다.");
  return result;
}
function notice(message) {
  $("notice").textContent = message;
}
function applyState(next) {
  state = next;
  serverOffset = next.server_time * 1000 - Date.now();
}
function scoreFor(id, part) {
  return (
    state.scores.find((s) => s.problem === id && s.part === part)?.score || 0
  );
}
function renderList() {
  $("problem-list").innerHTML = tasks
    .map(
      (t, i) =>
        `<button class="problem ${t.id === selected ? "selected" : ""}" data-problem="${t.id}" aria-current="${t.id === selected ? "true" : "false"}"><span class="problem-title">${String(i + 1).padStart(2, "0")} ${esc(t.title)}</span><span class="problem-meta">${t.category} · ${t.parts.reduce((n, p) => n + scoreFor(t.id, p.id), 0)} / ${t.parts.reduce((n, p) => n + p.max_score, 0)}점</span></button>`,
    )
    .join("");
  $("problem-list")
    .querySelectorAll("button")
    .forEach(
      (b) =>
        (b.onclick = () => {
          saveDrafts();
          selected = b.dataset.problem;
          render();
        }),
    );
}
function saveDrafts() {
  const t = tasks.find((t) => t.id === selected);
  if (t)
    for (const p of t.parts) {
      const input = $(`answer-${p.id}`);
      if (input && p.type !== "image")
        drafts.set(`${t.id}-${p.id}`, input.value);
    }
}
function render() {
  renderList();
  const t = tasks.find((t) => t.id === selected);
  if (!t) return;
  $("detail").innerHTML =
    `<span class="tag">${t.category} · 합성 연습 문제</span><h2>${esc(t.title)}</h2><div class="description">${esc(t.description)}</div><div class="toolbar"><button id="copy">문제 Markdown 복사</button><a href="/api/problems/${t.id}/dataset">데이터 묶음 다운로드 ↓</a><a href="${t.source}" target="_blank" rel="noopener noreferrer">유형 참고 글 ↗</a></div><div class="files">포함 파일: ${t.files.map(esc).join(" · ")}</div>` +
    t.parts
      .map(
        (p) =>
          `<form class="part" data-part="${p.id}"><div class="part-title"><h3><label for="answer-${p.id}">${p.id}. ${esc(p.prompt)}</label></h3><span class="score">최고 ${scoreFor(t.id, p.id)} / ${p.max_score}점</span></div>${p.type === "image" ? `<input id="answer-${p.id}" type="file" accept="image/png,image/jpeg" required>` : ["json", "markdown"].includes(p.type) ? `<textarea id="answer-${p.id}" required placeholder="${p.type === "json" ? "JSON 답안을 입력하세요" : "Markdown 보고서를 입력하세요"}">${esc(drafts.get(`${t.id}-${p.id}`) || "")}</textarea>` : `<input id="answer-${p.id}" type="${p.type === "number" ? "number" : "text"}" ${p.type === "number" ? 'step="any"' : ""} value="${esc(drafts.get(`${t.id}-${p.id}`) || "")}" required>`}<button class="primary" type="submit">제출 및 채점</button><div id="feedback-${p.id}" class="feedback" role="status"></div></form>`,
      )
      .join("") +
    `<div class="history"><h3>${t.id === "montage" ? "최근 4건의 이미지 평가" : "최근 제출 기록"}</h3><div id="history"></div></div>`;
  $("copy").onclick = async () => {
    try {
      const text = await (await fetch(`/api/problems/${t.id}/markdown`)).text();
      await navigator.clipboard.writeText(text);
      notice("문제 원문을 복사했습니다.");
    } catch {
      window.open(`/api/problems/${t.id}/markdown`, "_blank");
      notice("복사 권한이 없어 원문을 열었습니다. 직접 복사하세요.");
    }
  };
  $("detail")
    .querySelectorAll("form")
    .forEach(
      (form) =>
        (form.onsubmit = async (e) => {
          e.preventDefault();
          const p = t.parts.find((p) => p.id === form.dataset.part);
          const button = form.querySelector("button");
          button.disabled = true;
          try {
            const input = $(`answer-${p.id}`);
            let answer = input.value;
            if (p.type === "number") answer = Number(answer);
            if (p.type === "json") answer = JSON.parse(answer);
            if (p.type === "image") {
              const file = input.files[0];
              if (!file || file.size > 10 * 1024 * 1024)
                throw new Error("10MB 이하 이미지를 선택하세요.");
              answer = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(",")[1]);
                reader.onerror = () =>
                  reject(new Error("파일을 읽을 수 없습니다."));
                reader.readAsDataURL(file);
              });
            }
            const result = await api("/api/submit", {
              problem: t.id,
              part: p.id,
              answer,
            });
            applyState(result.state);
            saveDrafts();
            render();
            if (selected === t.id)
              $(`feedback-${p.id}`).textContent =
                `이번 점수: ${result.score}점\n${feedbackText(result.feedback)}`;
            notice("채점 완료. 하위 문항별 최고점이 유지됩니다.");
          } catch (err) {
            if (selected === t.id)
              $(`feedback-${p.id}`).textContent = err.message;
            else notice(err.message);
          } finally {
            button.disabled = false;
          }
        }),
    );
  const history = state.history
    .filter((h) => h.problem === t.id)
    .slice(0, t.id === "montage" ? 4 : 12);
  $("history").innerHTML = history.length
    ? history
        .map(
          (h) =>
            `<div class="history-row"><span>문항 ${h.part} · ${esc(new Date(h.created * 1000).toLocaleTimeString("ko-KR"))}<br>${esc(feedbackText(h.feedback))}</span><strong>${h.score}점</strong></div>`,
        )
        .join("")
    : '<p class="muted small">아직 제출 기록이 없습니다.</p>';
  const max = tasks.reduce(
    (n, t) => n + t.parts.reduce((n, p) => n + p.max_score, 0),
    0,
  );
  $("total").textContent =
    `${Math.round(state.scores.reduce((n, s) => n + s.score, 0) * 100) / 100} / ${max}점`;
  updateClock();
}
function feedbackText(f) {
  if (f.similarity !== undefined)
    return `유사도 ${f.similarity}% · ${Object.entries(f.regions)
      .map(([k, v]) => `${k} ${v}%`)
      .join(" / ")}`;
  if (f.structure !== undefined)
    return `구조 ${f.structure ? "✓" : "✗"} · API 이슈 ${f.api ? "✓" : "✗"} · 검색 이슈 ${f.search ? "✓" : "✗"} · 지난/미래 정보 제외 ${f.excludes ? "✓" : "✗"}`;
  return typeof f.correct === "boolean"
    ? f.correct
      ? "정답입니다."
      : "자료와 답안 조건을 다시 확인하세요."
    : `정답 항목 ${f.correct}개`;
}
function updateClock() {
  if (!state.mode) {
    $("clock").textContent = "연습을 시작하세요";
    return;
  }
  if (state.mode === "practice") {
    $("clock").textContent = "연습 모드 · 시간 제한 없음";
    return;
  }
  const left = Math.max(
    0,
    Math.ceil((state.expires * 1000 - Date.now() - serverOffset) / 1000),
  );
  $("clock").textContent = left
    ? `대회 · ${Math.floor(left / 3600)
        .toString()
        .padStart(2, "0")}:${Math.floor((left % 3600) / 60)
        .toString()
        .padStart(2, "0")}:${(left % 60).toString().padStart(2, "0")}`
    : "대회 종료 · 제출 마감";
}
async function start(mode) {
  if (
    state.mode &&
    !confirm("새 기록으로 시작할까요? 현재 기록은 이 화면에서 전환됩니다.")
  )
    return;
  try {
    applyState(await api("/api/session", { mode }));
    drafts.clear();
    render();
    notice(
      mode === "contest"
        ? "3시간 대회를 시작했습니다. 서버 시간이 제출 마감을 결정합니다."
        : "시간 제한 없이 연습할 수 있습니다.",
    );
  } catch (err) {
    notice(err.message);
  }
}
$("practice").onclick = () => start("practice");
$("contest").onclick = () => start("contest");
$("problems-tab").onclick = () => {
  $("workspace").hidden = false;
  $("ranking").hidden = true;
  $("problems-tab").classList.add("active");
  $("ranking-tab").classList.remove("active");
};
$("ranking-tab").onclick = async () => {
  try {
    const rows = await api("/api/ranking");
    $("rank-body").innerHTML = rows.length
      ? rows
          .map(
            (r) =>
              `<tr><td>${r.rank}</td><td>${esc(r.name)}</td><td>${r.score}</td></tr>`,
          )
          .join("")
      : '<tr><td colspan="3">아직 대회 제출 기록이 없습니다.</td></tr>';
    $("workspace").hidden = true;
    $("ranking").hidden = false;
    $("ranking-tab").classList.add("active");
    $("problems-tab").classList.remove("active");
  } catch (err) {
    notice(err.message);
  }
};
(async () => {
  try {
    [tasks, state] = await Promise.all([
      api("/api/problems"),
      api("/api/session"),
    ]);
    applyState(state);
    selected = tasks[0].id;
    render();
    setInterval(updateClock, 1000);
  } catch (err) {
    notice(err.message);
  }
})();
