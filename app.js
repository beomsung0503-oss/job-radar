const profile = window.JOB_RADAR_PROFILE;
const jobs = window.JOB_RADAR_JOBS || [];
const companies = window.JOB_RADAR_TARGET_COMPANIES || [];
const run = window.JOB_RADAR_RUN || {};

const els = {
  location: document.querySelector("#profile-location"),
  currentSalary: document.querySelector("#profile-current-salary"),
  targetRoles: document.querySelector("#profile-target-roles"),
  lastUpdated: document.querySelector("#last-updated"),
  pollingLabel: document.querySelector("#polling-label"),
  search: document.querySelector("#search-input"),
  fit: document.querySelector("#fit-filter"),
  source: document.querySelector("#source-filter"),
  score: document.querySelector("#score-filter"),
  scoreOutput: document.querySelector("#score-output"),
  total: document.querySelector("#metric-total"),
  recommended: document.querySelector("#metric-recommended"),
  stretch: document.querySelector("#metric-stretch"),
  megaventure: document.querySelector("#metric-megaventure"),
  companies: document.querySelector("#metric-companies"),
  resultCount: document.querySelector("#result-count"),
  companyCount: document.querySelector("#company-count"),
  jobsList: document.querySelector("#jobs-list"),
  companyList: document.querySelector("#company-list")
};

function formatDate(value) {
  if (!value) return "미수집";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function fitLabel(fit) {
  return {
    recommended: "추천",
    stretch: "스트레치",
    backup: "백업"
  }[fit] || fit;
}

function sourceLabel(job) {
  if (job.sourceQuality === "primary") return "원문급";
  if (job.sourceQuality === "adjacent") return "인접 후보";
  return job.source || "소스";
}

function salaryLabel(job) {
  if (job.salaryText) return job.salaryText;
  if (job.salaryStatus === "not_listed") return "공고 연봉 미기재";
  return "상세 연봉 미확인";
}

function companySizeLabel(job) {
  if (job.companySizeBand) return `${job.companySizeBand}명`;
  if (job.minCompanyEmployees) return `${job.minCompanyEmployees.toLocaleString("ko-KR")}명+`;
  return "규모 미확인";
}

function isAiVenture(item) {
  return (item.targetCompanyType || item.type || "").includes("ai-megaventure");
}

function isMegaVenture(item) {
  return (item.targetCompanyType || item.type || "").includes("megaventure");
}

function ventureLabel(item) {
  if (isAiVenture(item)) return "AI 메가벤처";
  if (isMegaVenture(item)) return "메가벤처";
  return "";
}

function openWorkSearchUrl(name) {
  return `https://www.google.com/search?q=${encodeURIComponent(`${name || ""} OpenWork 評判`)}`;
}

function openWorkLabel(item) {
  if (item.openWorkRating) return `OpenWork ${item.openWorkRating}`;
  return "OpenWork 확인";
}

function hasOfficialJobUrl(job) {
  return job.directUrlStatus === "verified_official" && Boolean(job.directUrl);
}

function actionButtons(job) {
  const openWork = `<a class="button secondary" href="${openWorkSearchUrl(job.targetCompany || job.company)}" target="_blank" rel="noreferrer">OpenWork</a>`;
  if (hasOfficialJobUrl(job)) {
    return `
      <a class="button" href="${job.directUrl}" target="_blank" rel="noreferrer">공고</a>
      <a class="button secondary" href="${job.url}" target="_blank" rel="noreferrer">LinkedIn</a>
      ${openWork}
    `;
  }
  return `<a class="button" href="${job.url}" target="_blank" rel="noreferrer">LinkedIn</a>${openWork}`;
}

function scoreBreakdown(job) {
  const breakdown = job.scoreBreakdown;
  if (!breakdown) return "";
  const max = breakdown.max || {};
  const notes = breakdown.notes || {};
  const items = [
    ["스킬", "skills"],
    ["직무", "role"],
    ["연차", "experience"],
    ["연봉", "salary"],
    ["지역", "location"],
    ["소스", "source"]
  ];

  return `
    <div class="score-grid">
      ${items.map(([label, key]) => {
        const value = Number(breakdown[key] || 0);
        const limit = Number(max[key] || 1);
        const width = Math.max(0, Math.min(100, (value / limit) * 100));
        return `
          <div class="score-part">
            <div class="score-part__top">
              <span>${label}</span>
              <strong>${value}/${limit}</strong>
            </div>
            <div class="score-bar" aria-hidden="true"><span style="width: ${width}%"></span></div>
            <small>${notes[key] || ""}</small>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function isVisible(job) {
  const query = els.search.value.trim().toLowerCase();
  const fit = els.fit.value;
  const source = els.source.value;
  const minScore = Number(els.score.value);
  const haystack = [
    job.title,
    job.company,
    job.location,
    job.salaryText,
    ...(job.reasons || []),
    ...(job.risks || [])
  ].join(" ").toLowerCase();

  if (query && !haystack.includes(query)) return false;
  if (fit !== "all" && job.fit !== fit) return false;
  if (source !== "all" && job.source !== source) return false;
  if ((job.score || 0) < minScore) return false;
  return true;
}

function badgeClass(fit) {
  if (fit === "recommended") return "badge good";
  if (fit === "stretch") return "badge warn";
  return "badge";
}

function renderJobs() {
  const visible = jobs
    .filter(isVisible)
    .sort((a, b) => (b.score || 0) - (a.score || 0));

  els.scoreOutput.textContent = `${els.score.value}+`;
  els.resultCount.textContent = `${visible.length}건`;

  if (!visible.length) {
    els.jobsList.innerHTML = `<div class="empty-state">조건에 맞는 후보가 없습니다.</div>`;
    return;
  }

  els.jobsList.innerHTML = visible.map((job) => {
    const reasons = (job.reasons || []).map((item) => `<li>${item}</li>`).join("");
    const risks = (job.risks || []).map((item) => `<li>${item}</li>`).join("");
    const salary = salaryLabel(job);
    return `
      <article class="job-card">
        <div class="job-title-row">
          <div>
            <h3>${job.title}</h3>
            <div class="job-meta">${job.company} · ${companySizeLabel(job)} · ${job.location} · ${salary} · ${job.postedDate || "날짜 미기재"}</div>
          </div>
          <div class="score">${job.score}</div>
        </div>
        <div class="badge-row">
          <span class="${badgeClass(job.fit)}">${fitLabel(job.fit)}</span>
          <span class="badge">${job.source}</span>
          <span class="badge">${sourceLabel(job)}</span>
          <span class="badge">${job.employmentType || "고용형태 미기재"}</span>
          <span class="badge good">${companySizeLabel(job)}</span>
          ${ventureLabel(job) ? `<span class="badge ai">${ventureLabel(job)}</span>` : ""}
          <span class="badge">${openWorkLabel(job)}</span>
        </div>
        <ul class="reason-list">${reasons}</ul>
        <ul class="risk-list">${risks}</ul>
        ${scoreBreakdown(job)}
        <div class="card-actions">
          ${actionButtons(job)}
        </div>
      </article>
    `;
  }).join("");
}

function renderCompanies() {
  els.companyCount.textContent = `${companies.length}개`;
  els.companies.textContent = String(companies.length);
  els.companyList.innerHTML = companies.map((company) => {
    const terms = company.watchTerms.map((term) => `<span>${term}</span>`).join("");
    return `
      <article class="company-item">
        <div class="company-name-row">
          <strong>${company.name}</strong>
          <span class="priority">${company.priority}</span>
        </div>
        <span class="company-meta">${company.type} · ${company.employeeBand || "1000+"}명 · ${openWorkLabel(company)}</span>
        <div class="term-row">${terms}</div>
        <div class="card-actions compact">
          <a class="button secondary" href="${company.officialCareersUrl}" target="_blank" rel="noreferrer">공식 Careers</a>
          <a class="button secondary" href="${openWorkSearchUrl(company.name)}" target="_blank" rel="noreferrer">OpenWork</a>
        </div>
      </article>
    `;
  }).join("");
}

function renderMetrics() {
  els.total.textContent = String(jobs.length);
  els.recommended.textContent = String(jobs.filter((job) => job.fit === "recommended").length);
  els.stretch.textContent = String(jobs.filter((job) => job.fit === "stretch").length);
  els.megaventure.textContent = String(jobs.filter(isMegaVenture).length);
}

function renderProfile() {
  els.location.textContent = profile.baseLocation;
  els.currentSalary.textContent = `${profile.currentSalaryJpyMan}만 엔`;
  els.targetRoles.textContent = profile.targetRoles.slice(0, 4).join(" · ");
  els.lastUpdated.textContent = `마지막 수집 ${formatDate(run.generatedAt)}`;
  els.pollingLabel.textContent = `${run.recommendedPollingMinutes || 180}분 폴링`;
}

function bindFilters() {
  [els.search, els.fit, els.source, els.score].forEach((el) => {
    el.addEventListener("input", renderJobs);
    el.addEventListener("change", renderJobs);
  });
}

renderProfile();
renderMetrics();
renderCompanies();
renderJobs();
bindFilters();
