import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
JOBS_JS = DATA_DIR / "jobs.js"

LINKEDIN_QUERIES = [
    "Salesforce Consultant",
    "Salesforce コンサルタント",
    "Salesforce Project Manager",
    "Salesforce PM",
    "CRM Consultant Salesforce",
    "Salesforce Presales",
    "Salesforce プリセールス",
    "Salesforce Customer Success",
    "Slack Salesforce Consultant",
]

def load_target_companies():
    target_file = DATA_DIR / "target_companies.js"
    if not target_file.exists():
        return []
    text = target_file.read_text(encoding="utf-8")
    companies = []
    for block in re.findall(r"\{(.*?)\}", text, flags=re.S):
        name = find_one(r'name:\s*"([^"]+)"', block)
        url = find_one(r'officialCareersUrl:\s*"([^"]+)"', block)
        terms_block = find_one(r"watchTerms:\s*\[(.*?)\]", block)
        terms = re.findall(r'"([^"]+)"', terms_block)
        if name and url and terms:
            companies.append((name, url, terms))
    return companies


def load_company_careers_map():
    return {name.lower(): url for name, url, _terms in load_target_companies()}

EXCLUDE_TITLE_TERMS = [
    "Engineer",
    "エンジニア",
    "技術者",
    "Software Engineer",
    "Application Engineer",
    "Solution Engineer",
    "Solutions Engineer",
    "Sales Engineer",
    "Pre-Sales Engineer",
    "Developer",
    "開発者",
    "開発エンジニア",
    "開発リーダー",
    "開発担当",
    "開発PM",
    "Backend",
    "Frontend",
    "DevOps",
    "SRE",
    "Architect",
    "Admin",
    "Administrator",
    "アドミン",
    "管理者",
    "システム管理",
    "社内SE",
    "システムエンジニア",
]

CORE_TITLE_TERMS = [
    "Salesforce",
    "CRM",
    "Agentforce",
    "Slack",
    "Sales Cloud",
    "Service Cloud",
    "Marketing Cloud",
]

TARGET_ROLE_TITLE_TERMS = [
    "Consultant",
    "コンサル",
    "PM",
    "PL",
    "Project Manager",
    "プロジェクトマネージャ",
    "プロジェクトマネジャ",
    "Presales",
    "Pre-Sales",
    "プリセールス",
    "Customer Success",
    "カスタマーサクセス",
    "Implementation",
    "導入",
    "DX推進",
    "業務改革",
    "Solution Consultant",
    "Technical Consultant",
]

MATCH_TERMS = [
    "Salesforce",
    "CRM",
    "Sales Cloud",
    "Agentforce",
    "Slack",
    "Flow",
    "Apex",
    "Visualforce",
    "PM",
    "PL",
    "Consultant",
    "コンサル",
    "Implementation",
    "Presales",
    "プリセールス",
    "Customer Success",
    "DX",
]

CANDIDATE_PROFILE = {
    "salesforce_years": 2.2,
    "pm_years": 1.0,
    "current_salary_man": 500,
    "target_salary_man": 600,
}

ROLE_TITLE_PATTERNS = [
    r"\bConsultant\b",
    r"コンサル",
    r"\bProject\s*Manager\b",
    r"プロジェクトマネージャ",
    r"\bCustomer\s*Success\b",
    r"\bPresales\b",
    r"\bPre-Sales\b",
    r"プリセールス",
    r"\bImplementation\b",
    r"導入",
    r"\bSolution\s*Consultant\b",
    r"\bTechnical\s*Consultant\b",
]

CONTENT_LINK_PREFIXES = (
    "explore ",
    "learn ",
    "ask ",
    "help",
    "blog",
    "resource",
    "webinar",
)


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,ko;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as res:
        return res.read().decode("utf-8", "replace")


def strip_tags(value):
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def find_one(pattern, text):
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return ""
    return strip_tags(match.group(1) if match.lastindex else match.group(0))


def parse_linkedin_cards(page):
    cards = []
    for block in re.findall(r'<div class="base-card.*?</li>', page, flags=re.I | re.S):
        job_id = find_one(r'data-entity-urn="urn:li:jobPosting:([^"]+)"', block)
        url = html.unescape(find_one(r'<a class="base-card__full-link[^"]*" href="([^"]+)"', block))
        title = find_one(r'<h3 class="base-search-card__title">\s*(.*?)\s*</h3>', block)
        company = find_one(r'<h4 class="base-search-card__subtitle">\s*(.*?)\s*</h4>', block)
        location = find_one(r'<span class="job-search-card__location">\s*(.*?)\s*</span>', block)
        list_date = find_one(r'<time[^>]*datetime="([^"]+)"', block)
        benefit = find_one(r'<span class="job-posting-benefits__text">\s*(.*?)\s*</span>', block)
        if title and url:
            cards.append(
                {
                    "id": f"linkedin-{job_id or abs(hash(url))}",
                    "source": "LinkedIn",
                    "sourceQuality": "primary",
                    "title": title,
                    "company": company,
                    "location": location,
                    "postedDate": list_date,
                    "salaryText": "",
                    "salaryStatus": "unknown",
                    "employmentType": "Full-time" if "Japan" in location else "",
                    "seniority": "",
                    "jobFunction": "",
                    "url": url.split("?")[0],
                    "directUrl": "",
                    "directUrlStatus": "search_required",
                    "directSearchUrl": "",
                    "status": "open",
                    "fit": "backup",
                    "score": 0,
                    "reasons": [benefit] if benefit else [],
                    "risks": ["LinkedIn 상세/지원 버튼은 로그인 후 재확인 필요"],
                }
            )
    return cards


def normalize_company_name(value):
    return re.sub(r"\s+", " ", value or "").strip().lower()


def build_search_url(job):
    query = f'"{job.get("title", "")}" "{job.get("company", "")}" 採用 OR careers'
    return "https://www.google.com/search?q=" + urllib.parse.quote(query)


def add_direct_destination(job, careers_map):
    title = job.get("title", "")
    company = job.get("company", "")
    company_key = normalize_company_name(company)

    if "virtualex" in company_key or "バーチャレクス" in company:
        if "crm" in title.lower() or "Salesforce" in title or "DX推進" in title:
            job["directUrl"] = "https://hrmos.co/pages/virtualex/jobs/0000090"
            job["directUrlStatus"] = "verified_official"
            job["directSource"] = "HRMOS official"
            job["reasons"].append("LinkedIn 없이 열 수 있는 공식 HRMOS 공고 확인")
            return job

    for name, careers_url in careers_map.items():
        if name and (name in company_key or company_key in name):
            job["directUrl"] = careers_url
            job["directUrlStatus"] = "company_careers"
            job["directSource"] = "Company careers"
            job["risks"].append("회사 Careers까지 연결됨; 동일 공고 매칭은 추가 확인 필요")
            return job

    job["directSearchUrl"] = build_search_url(job)
    job["directUrlStatus"] = "search_required"
    return job


def parse_linkedin_detail(page):
    text = strip_tags(page)
    criteria = {}
    for item in re.findall(r'<li class="description__job-criteria-item">(.*?)</li>', page, flags=re.I | re.S):
        key = find_one(r"<h3[^>]*>\s*(.*?)\s*</h3>", item)
        value = find_one(r"<span[^>]*>\s*(.*?)\s*</span>", item)
        if key and value:
            criteria[key] = value

    description = find_one(r'<div class="show-more-less-html__markup[^"]*">\s*(.*?)\s*</div>', page)
    if not description:
        description = text

    return {
        "salaryText": extract_salary(description),
        "employmentType": criteria.get("Employment type", ""),
        "seniority": criteria.get("Seniority level", ""),
        "jobFunction": criteria.get("Job function", ""),
        "descriptionText": description[:1400],
    }


def extract_salary(text):
    normalized = re.sub(r"\s+", " ", text)
    patterns = [
        r"(?:想定年収|予定年収|年収|給与)\s*[:：]?\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*[~〜～\-－]\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*円?",
        r"(?:月給|月収)\s*[:：]?\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*[~〜～\-－]\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*円?",
        r"(?:Annual salary|Salary|Compensation)\s*[:：]?\s*(?:JPY|¥|円)?\s*[0-9,]+(?:\.[0-9]+)?\s*[~〜～\-－]\s*(?:JPY|¥|円)?\s*[0-9,]+(?:\.[0-9]+)?",
        r"(?:年俸)\s*[:：]?\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*[~〜～\-－]\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*円?",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.I)
        if match:
            return match.group(0).strip(" 、。")
    return ""


def salary_numbers_man(salary_text):
    if not salary_text:
        return []
    normalized = salary_text.replace(",", "")
    nums = [float(value) for value in re.findall(r"[0-9]+(?:\.[0-9]+)?", normalized)]
    if not nums:
        return []
    if "月給" in salary_text or "月収" in salary_text:
        return [value * 12 for value in nums]
    if any(value >= 10000 for value in nums):
        return [value / 10000 for value in nums]
    return nums


def infer_required_years(text):
    normalized = re.sub(r"\s+", " ", text)
    candidates = []
    patterns = [
        r"([0-9]+)\s*年以上",
        r"([0-9]+)\s*年\s*以上",
        r"([0-9]+)\+\s*years?",
        r"([0-9]+)\s*or more years?",
        r"at least\s*([0-9]+)\s*years?",
        r"([0-9]+)\s*年以上の.*?(?:経験|PM|PL|コンサル)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, flags=re.I):
            try:
                value = int(match.group(1))
            except ValueError:
                continue
            if 1 <= value <= 15:
                candidates.append(value)
    if not candidates:
        return None
    return max(candidates)


def contains_term(text, term):
    if not text or not term:
        return False
    if term in {"PM", "PL"}:
        separated = re.search(rf"(?:^|[^A-Za-z]){re.escape(term)}(?:$|[^A-Za-z])", text)
        attached_to_domain = re.search(
            rf"(?:Salesforce|CRM|DX|導入|プロジェクト)\s*{re.escape(term)}",
            text,
            flags=re.I,
        )
        return bool(separated or attached_to_domain)
    return term.lower() in text.lower()


def contains_any(text, terms):
    return any(contains_term(text, term) for term in terms)


def score_cap(value, cap):
    return min(value, cap)


def detailed_score_job(job):
    title = job.get("title", "")
    description = job.get("descriptionText", "")
    salary_text = job.get("salaryText", "")
    text = " ".join(
        [
            title,
            job.get("company", ""),
            job.get("location", ""),
            job.get("seniority", ""),
            job.get("jobFunction", ""),
            salary_text,
            description,
            " ".join(job.get("reasons", [])),
        ]
    )

    excluded_title_hit = next((term for term in EXCLUDE_TITLE_TERMS if term.lower() in title.lower()), "")
    if excluded_title_hit:
        return None

    core_title_match = contains_any(title, CORE_TITLE_TERMS)
    target_role_title_match = contains_any(title, TARGET_ROLE_TITLE_TERMS)
    off_target_title = contains_any(
        title,
        ["SAP", "ServiceNow", "Dynamics", "Power Platform", "Oracle", "Adobe"],
    ) and not core_title_match

    skills = 0
    skill_hits = []
    skill_weights = [
        ("Salesforce", 10),
        ("CRM", 5),
        ("Sales Cloud", 4),
        ("Service Cloud", 4),
        ("Marketing Cloud", 4),
        ("Agentforce", 5),
        ("Slack", 5),
        ("Flow", 3),
        ("Apex", 3),
        ("Visualforce", 3),
        ("Data Cloud", 3),
        ("MuleSoft", 2),
    ]
    for term, points in skill_weights:
        if term.lower() in text.lower():
            skills += points
            skill_hits.append(term)
    skills = score_cap(skills, 30)

    role = 0
    role_hits = []
    role_weights = [
        (["Consultant", "コンサル"], "컨설턴트", 8),
        (["PM", "PL", "Project Manager", "プロジェクトマネージャ"], "PM/PL", 7),
        (["Implementation", "導入", "要件定義", "定着"], "도입/정착", 5),
        (["Presales", "Pre-Sales", "プリセールス"], "프리세일즈", 4),
        (["Customer Success", "カスタマーサクセス"], "CS", 4),
        (["DX", "業務改革", "Business transformation"], "DX/업무개혁", 3),
    ]
    for terms, label, points in role_weights:
        if contains_any(text, terms):
            role += points
            role_hits.append(label)
    if target_role_title_match:
        role += 4
        role_hits.append("타이틀 매칭")
    if contains_any(title, ["Sales", "営業"]) and not contains_any(title, ["Salesforce", "Sales Cloud"]):
        role -= 6
    if off_target_title:
        role -= 8
    role = max(0, score_cap(role, 25))

    required_years = infer_required_years(text)
    senior_title = contains_any(title, ["Senior", "シニア", "Manager", "マネージャー", "責任者", "Lead"])
    if required_years is None:
        experience = 12
        experience_note = "연차 요건 미확인"
    elif required_years <= 2:
        experience = 20
        experience_note = f"요구 {required_years}년"
    elif required_years == 3:
        experience = 16
        experience_note = "요구 3년"
    elif required_years == 4:
        experience = 12
        experience_note = "요구 4년"
    elif required_years == 5:
        experience = 8
        experience_note = "요구 5년"
    else:
        experience = 4
        experience_note = f"요구 {required_years}년 이상"
    if senior_title and required_years is None:
        experience = min(experience, 9)
        experience_note = "시니어/매니저 타이틀"
    elif senior_title and required_years and required_years >= 4:
        experience = max(0, experience - 3)
        experience_note += " + 시니어"

    salary_values = salary_numbers_man(salary_text)
    if salary_values:
        low = min(salary_values)
        high = max(salary_values)
        if low >= CANDIDATE_PROFILE["target_salary_man"]:
            salary = 10
            salary_note = "목표연봉 이상"
        elif high >= CANDIDATE_PROFILE["target_salary_man"]:
            salary = 8
            salary_note = "목표연봉 포함"
        elif high >= CANDIDATE_PROFILE["current_salary_man"]:
            salary = 5
            salary_note = "현재연봉 이상"
        else:
            salary = 2
            salary_note = "연봉 상승 제한"
    elif job.get("salaryStatus") == "not_listed":
        salary = 5
        salary_note = "공고 연봉 미기재"
    else:
        salary = 4
        salary_note = "상세 연봉 미확인"

    location = 0
    loc_hits = []
    if contains_any(text, ["Tokyo", "東京", "Japan", "日本"]):
        location += 5
        loc_hits.append("일본/도쿄")
    if contains_any(text, ["Remote", "リモート", "在宅", "Hybrid", "ハイブリッド"]):
        location += 2
        loc_hits.append("리모트/하이브리드")
    if contains_any(text, ["Japanese", "日本語", "English", "英語", "Global"]):
        location += 3
        loc_hits.append("언어/글로벌")
    else:
        location += 1
    location = score_cap(location, 10)

    source = 0
    if job.get("directUrlStatus") == "verified_official":
        source = 5
        source_note = "공식 공고"
    elif job.get("source") == "LinkedIn":
        source = 3
        source_note = "LinkedIn"
    else:
        source = 2
        source_note = "보조 소스"

    total = skills + role + experience + salary + location + source
    if off_target_title:
        total = max(0, total - 8)
    risks = []
    if required_years and required_years >= 5:
        risks.append(f"필수/우대 연차가 높음({required_years}년)")
    if senior_title:
        risks.append("시니어/매니저급 포지션")
    if not salary_values:
        risks.append(salary_note)
    if job.get("directUrlStatus") != "verified_official":
        risks.append("공식 상세 URL 미확인")
    if off_target_title:
        risks.append("제목이 Salesforce/CRM 중심이 아님")
    if core_title_match and not target_role_title_match:
        risks.append("제목의 목표 직무명 불명확")

    positives = []
    if skill_hits:
        positives.append("스킬: " + ", ".join(skill_hits[:5]))
    if role_hits:
        positives.append("직무: " + ", ".join(dict.fromkeys(role_hits)))
    if loc_hits:
        positives.append("조건: " + ", ".join(loc_hits))

    breakdown = {
        "skills": skills,
        "role": role,
        "experience": experience,
        "salary": salary,
        "location": location,
        "source": source,
        "total": total,
        "max": {
            "skills": 30,
            "role": 25,
            "experience": 20,
            "salary": 10,
            "location": 10,
            "source": 5,
        },
        "notes": {
            "skills": ", ".join(skill_hits[:8]) or "핵심 스킬 약함",
            "role": ", ".join(dict.fromkeys(role_hits)) or "직무 방향 약함",
            "experience": experience_note,
            "salary": salary_note,
            "location": ", ".join(loc_hits) or "지역/언어 정보 적음",
            "source": source_note,
        },
        "flags": {
            "coreTitleMatch": core_title_match,
            "targetRoleTitleMatch": target_role_title_match,
            "offTargetTitle": off_target_title,
        },
    }
    return total, breakdown, positives, risks


def enrich_linkedin_details(jobs, detail_limit):
    if detail_limit <= 0:
        return jobs

    candidates = sorted(jobs, key=lambda item: score_job(item), reverse=True)[:detail_limit]
    by_id = {job["id"]: job for job in jobs}
    for job in candidates:
        raw_id = job["id"].replace("linkedin-", "", 1)
        if not raw_id.isdigit():
            continue
        detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{raw_id}"
        try:
            detail = parse_linkedin_detail(fetch(detail_url))
        except Exception as exc:
            job["risks"].append(f"상세 파싱 실패: {exc}")
            time.sleep(1.5)
            continue

        if detail.get("salaryText"):
            job["salaryText"] = detail["salaryText"]
            job["salaryStatus"] = "listed"
            job["reasons"].append("상세 본문에서 연봉 정보 확인")
        else:
            job["salaryStatus"] = "not_listed"
            job["risks"].append("LinkedIn 공개 상세에 연봉 정보 없음")

        for key in ["employmentType", "seniority", "jobFunction", "descriptionText"]:
            if detail.get(key):
                job[key] = detail[key]
        by_id[job["id"]] = job
        time.sleep(1.5)
    return list(by_id.values())


def collect_linkedin(max_queries):
    rows = {}
    careers_map = load_company_careers_map()
    for query in LINKEDIN_QUERIES[:max_queries]:
        params = {
            "keywords": query,
            "location": "Japan",
            "f_TPR": "r2592000",
            "start": "0",
        }
        url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(params)
        try:
            for row in parse_linkedin_cards(fetch(url)):
                row = add_direct_destination(row, careers_map)
                rows.setdefault(row["id"], row)
        except Exception as exc:
            print(f"[warn] LinkedIn query failed: {query}: {exc}", file=sys.stderr)
        time.sleep(1.2)
    return list(rows.values())


def absolute_url(base, href):
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urllib.parse.urljoin(base, href)


def collect_official(max_companies):
    rows = []
    target_companies = load_target_companies()
    for company, url, terms in target_companies[:max_companies]:
        try:
            page = fetch(url)
        except Exception as exc:
            print(f"[warn] Official page failed: {company}: {exc}", file=sys.stderr)
            continue

        found = set()
        for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, flags=re.I | re.S):
            href, body = match.groups()
            text = strip_tags(body)
            if len(text) < 4:
                continue
            if text.lower().startswith(CONTENT_LINK_PREFIXES):
                continue
            haystack = f"{text} {href}"
            if not any(term.lower() in haystack.lower() for term in terms):
                continue
            if not any(re.search(pattern, text, flags=re.I) for pattern in ROLE_TITLE_PATTERNS):
                continue
            if any(term.lower() in text.lower() for term in EXCLUDE_TITLE_TERMS):
                continue
            link = absolute_url(url, html.unescape(href))
            key = (company, text, link)
            if key in found:
                continue
            found.add(key)
            rows.append(
                {
                    "id": f"official-{abs(hash(key))}",
                    "source": "Official",
                    "sourceQuality": "official",
                    "title": text[:160],
                    "company": company,
                    "location": "Japan",
                    "postedDate": "",
                    "salaryText": "",
                    "employmentType": "",
                    "seniority": "",
                    "jobFunction": "",
                    "url": link,
                    "directUrl": link,
                    "directUrlStatus": "verified_official",
                    "directSearchUrl": "",
                    "status": "open",
                    "fit": "backup",
                    "score": 0,
                    "reasons": ["공식 Careers 페이지에서 키워드 링크 발견"],
                    "risks": ["일반 HTML 스캔 결과라 상세 직무 페이지 여부 확인 필요"],
                }
            )
        time.sleep(1.0)
    return rows


def score_job(job):
    scored = detailed_score_job(job)
    if scored is None:
        return -1
    return scored[0]


def classify(job):
    score = job["score"]
    breakdown = job.get("scoreBreakdown", {})
    experience = breakdown.get("experience", 0)
    role = breakdown.get("role", 0)
    flags = breakdown.get("flags", {})
    if (
        score >= 66
        and experience >= 12
        and role >= 10
        and flags.get("coreTitleMatch")
        and flags.get("targetRoleTitleMatch")
    ):
        return "recommended"
    if score >= 55:
        return "stretch"
    return "backup"


def merge_existing(new_jobs):
    existing = []
    if JOBS_JS.exists():
        text = JOBS_JS.read_text(encoding="utf-8")
        match = re.search(
            r"window\.JOB_RADAR_JOBS\s*=\s*(\[.*?\]);\s*window\.JOB_RADAR_RUN",
            text,
            flags=re.S,
        )
        if not match:
            match = re.search(r"window\.JOB_RADAR_JOBS\s*=\s*(\[.*\]);\s*$", text, flags=re.S)
        if match:
            try:
                existing = json.loads(match.group(1))
            except json.JSONDecodeError:
                existing = []

    merged = {job["url"]: job for job in existing}
    for job in new_jobs:
        merged[job["url"]] = job
    return list(merged.values())


def write_jobs_js(jobs):
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")
    payload = json.dumps(jobs, ensure_ascii=False, indent=2)
    run = {
        "generatedAt": now,
        "mode": "collector-run",
        "recommendedPollingMinutes": 180,
        "notes": [
            "LinkedIn public search is rate-limited; avoid aggressive polling.",
            "Official Careers collection uses conservative keyword link scanning.",
            "求人ボックス is intentionally not used as a primary source.",
        ],
    }
    JOBS_JS.write_text(
        "window.JOB_RADAR_JOBS = "
        + payload
        + ";\n\nwindow.JOB_RADAR_RUN = "
        + json.dumps(run, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--linkedin-queries", type=int, default=5)
    parser.add_argument("--linkedin-detail-limit", type=int, default=24)
    parser.add_argument("--official-companies", type=int, default=0)
    parser.add_argument("--no-linkedin", action="store_true")
    parser.add_argument("--no-official", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    new_jobs = []
    if not args.no_linkedin:
        linkedin_jobs = collect_linkedin(args.linkedin_queries)
        new_jobs.extend(enrich_linkedin_details(linkedin_jobs, args.linkedin_detail_limit))
    if not args.no_official:
        new_jobs.extend(collect_official(args.official_companies))

    filtered = []
    for job in new_jobs:
        scored = detailed_score_job(job)
        if scored is None:
            continue
        score, breakdown, positives, scoring_risks = scored
        job["score"] = score
        job["scoreBreakdown"] = breakdown
        job["fit"] = classify(job)
        job["reasons"] = list(dict.fromkeys((job.get("reasons") or []) + positives))
        job["risks"] = list(dict.fromkeys((job.get("risks") or []) + scoring_risks))
        filtered.append(job)

    if not filtered and JOBS_JS.exists():
        print("No new jobs collected; keeping existing dashboard data.")
        return

    merged = filtered if args.replace else merge_existing(filtered)
    merged.sort(key=lambda item: (item.get("score", 0), item.get("postedDate", "")), reverse=True)
    write_jobs_js(merged[:80])
    print(f"Wrote {len(merged[:80])} jobs to {JOBS_JS}")


if __name__ == "__main__":
    main()
