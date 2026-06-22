import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
JOBS_JS = DATA_DIR / "jobs.js"

COLLECTION_STATS = {
    "linkedinSearchRequests": 0,
    "linkedinSearchSucceeded": 0,
    "linkedinSearchFailed": 0,
    "linkedinDetailRequests": 0,
    "linkedinDetailFailed": 0,
    "officialRequests": 0,
    "officialFailed": 0,
}

LINKEDIN_QUERIES = [
    "Salesforce Consultant",
    "Salesforce コンサルタント",
    "Salesforce 導入コンサルタント",
    "Salesforce シニアコンサルタント",
    "Salesforce Project Manager",
    "Salesforce PM",
    "Salesforce プロジェクトマネージャー",
    "Salesforce プロジェクトリーダー",
    "CRM Consultant Salesforce",
    "CRM コンサルタント Salesforce",
    "CRM PM Salesforce",
    "CX CRM Consultant",
    "Salesforce Presales",
    "Salesforce プリセールス",
    "Salesforce Customer Success",
    "Salesforce カスタマーサクセス",
    "Salesforce Implementation Consultant",
    "Sales Cloud Consultant",
    "Service Cloud Consultant",
    "Agentforce Consultant",
    "Slack Salesforce Consultant",
    "AI Solution Consultant",
    "AI Customer Success",
    "AI Project Manager",
    "AI DX Consultant",
    "AI Implementation Consultant",
]

MEGAVENTURE_ROLE_QUERIES = [
    "Customer Success",
    "Solution Consultant",
    "Implementation Consultant",
    "Project Manager",
]


def rotated_slice(items, count, rotation_slot):
    if not items or count <= 0:
        return []
    count = min(count, len(items))
    start = (rotation_slot * count) % len(items)
    return [items[(start + index) % len(items)] for index in range(count)]

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
        aliases_block = find_one(r"aliases:\s*\[(.*?)\]", block)
        aliases = re.findall(r'"([^"]+)"', aliases_block) if aliases_block else []
        min_employees = find_one(r"minEmployees:\s*([0-9]+)", block)
        employee_band = find_one(r'employeeBand:\s*"([^"]+)"', block) or "1000+"
        company_type = find_one(r'type:\s*"([^"]+)"', block)
        priority = find_one(r'priority:\s*"([^"]+)"', block)
        if name and url and terms:
            companies.append(
                {
                    "name": name,
                    "url": url,
                    "terms": terms,
                    "aliases": aliases,
                    "minEmployees": int(min_employees or 0),
                    "employeeBand": employee_band,
                    "type": company_type,
                    "priority": priority,
                }
            )
    return companies


def load_company_careers_map():
    return load_target_companies()

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

EXCLUDE_COMPANY_TERMS = [
    "Computer Futures",
    "Michael Page",
    "Robert Walters",
    "Hays",
    "en world",
    "JAC Recruitment",
    "Morgan McKinley",
    "Randstad",
    "Adecco",
]

CORE_TITLE_TERMS = [
    "Salesforce",
    "CRM",
    "Agentforce",
    "AI",
    "生成AI",
    "LLM",
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
    "AI",
    "生成AI",
    "LLM",
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
    "min_company_employees": 1000,
    "min_ai_venture_employees": 500,
}

TOKYO_SCOPE_TERMS = [
    "Tokyo",
    "東京",
    "Minato",
    "Chiyoda",
    "Chuo-ku",
    "Shibuya",
    "Shinjuku",
    "Shinagawa",
    "Akasaka",
    "Roppongi",
    "Remote",
    "リモート",
    "在宅",
    "Hybrid",
    "ハイブリッド",
]

NON_TOKYO_LOCATION_TERMS = [
    "Osaka",
    "大阪",
    "Fukuoka",
    "福岡",
    "Nagoya",
    "名古屋",
    "Kyoto",
    "京都",
    "Kobe",
    "神戸",
    "Sapporo",
    "札幌",
    "Sendai",
    "仙台",
    "Hiroshima",
    "広島",
    "Yokohama",
    "横浜",
    "Kanagawa",
    "神奈川",
]

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


def fetch(url, timeout=25):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,ko;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
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
    value = unicodedata.normalize("NFKC", value or "")
    value = value.lower()
    value = re.sub(r"株式会社|有限会社|\(株\)|（株）|corporation|corp\.?|inc\.?|co\.,?\s*ltd\.?|llc|合同会社|日本法人", " ", value)
    value = re.sub(r"[^0-9a-zぁ-んァ-ン一-龥]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def company_target_names(target):
    return [target.get("name", ""), *target.get("aliases", [])]


def company_matches_target(company, target):
    company_key = normalize_company_name(company)
    if not company_key:
        return False
    for candidate in company_target_names(target):
        candidate_key = normalize_company_name(candidate)
        if not candidate_key:
            continue
        if candidate_key == company_key:
            return True
        if len(candidate_key) >= 7 and len(company_key) >= 7:
            if candidate_key in company_key or company_key in candidate_key:
                return True
    return False


def is_megaventure_target(job_or_target):
    return "megaventure" in (job_or_target.get("type") or job_or_target.get("targetCompanyType") or "")


def is_ai_venture_target(job_or_target):
    return "ai-megaventure" in (job_or_target.get("type") or job_or_target.get("targetCompanyType") or "")


def required_company_floor(job):
    if is_megaventure_target(job):
        return CANDIDATE_PROFILE["min_ai_venture_employees"]
    return CANDIDATE_PROFILE["min_company_employees"]


def company_scale_allowed(job):
    return job.get("minCompanyEmployees", 0) >= required_company_floor(job)


def is_tokyo_scope(job):
    title_location = " ".join([job.get("title", ""), job.get("location", "")])
    if contains_any(title_location, NON_TOKYO_LOCATION_TERMS):
        return False
    text = " ".join(
        [
            title_location,
            job.get("descriptionText", ""),
            " ".join(job.get("reasons", [])),
        ]
    )
    return contains_any(text, TOKYO_SCOPE_TERMS)


def infer_company_scale(job):
    if company_scale_allowed(job):
        return job

    text = " ".join(
        [
            job.get("company", ""),
            job.get("descriptionText", ""),
            " ".join(job.get("reasons", [])),
        ]
    )
    if re.search(r"(?:Fortune|フォーチュン)\s*(?:Global\s*)?500", text, flags=re.I):
        job["minCompanyEmployees"] = required_company_floor(job)
        job["companySizeBand"] = "500+" if is_ai_venture_target(job) else "1000+"
        job["companyScaleStatus"] = "inferred_large"
        job["reasons"].append("회사 규모: Fortune/Global 500급 신호")
    elif re.search(r"(?:over|more than|超过|従業員|社員|employees?|people)\s*[0-9,]{4,}", text, flags=re.I):
        job["minCompanyEmployees"] = required_company_floor(job)
        job["companySizeBand"] = "500+" if is_ai_venture_target(job) else "1000+"
        job["companyScaleStatus"] = "inferred_large"
        job["reasons"].append(f"회사 규모: 본문에서 {required_company_floor(job)}명 이상 신호")
    else:
        job.setdefault("minCompanyEmployees", 0)
        job.setdefault("companySizeBand", "미확인")
        job.setdefault("companyScaleStatus", "unverified")
    return job


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
            job["minCompanyEmployees"] = 0
            job["companySizeBand"] = "미확인"
            job["companyScaleStatus"] = "unverified"
            return job

    for target in careers_map:
        if company_matches_target(company, target):
            job["directUrl"] = target["url"]
            job["directUrlStatus"] = "company_careers"
            job["directSource"] = "Company careers"
            job["targetCompany"] = target["name"]
            job["targetCompanyType"] = target.get("type", "")
            job["minCompanyEmployees"] = target.get("minEmployees", 0)
            job["companySizeBand"] = target.get("employeeBand", "1000+")
            if company_scale_allowed(job):
                job["companyScaleStatus"] = "megaventure_500_plus" if is_megaventure_target(job) else "target_1000_plus"
                job["reasons"].append(f"회사 규모: {job['companySizeBand']} 대상 회사")
            else:
                job["companyScaleStatus"] = "below_required_size"
            job["risks"].append("회사 Careers까지 연결됨; 동일 공고 매칭은 추가 확인 필요")
            return job

    job["directSearchUrl"] = build_search_url(job)
    job["directUrlStatus"] = "search_required"
    job["companySizeBand"] = "미확인"
    job["minCompanyEmployees"] = 0
    job["companyScaleStatus"] = "unverified"
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
    if contains_any(job.get("company", ""), EXCLUDE_COMPANY_TERMS):
        return None

    infer_company_scale(job)
    if not company_scale_allowed(job):
        return None
    if not is_tokyo_scope(job):
        return None

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
        ("AI", 4),
        ("生成AI", 4),
        ("LLM", 4),
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
        (["AI", "生成AI", "LLM", "Artificial Intelligence"], "AI", 4),
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
    if contains_any(text, ["Tokyo", "東京"]):
        location += 5
        loc_hits.append("도쿄")
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
    if job.get("companyScaleStatus") == "inferred_large":
        risks.append("회사 규모는 본문 신호 기반 추정")
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
    positives.append(f"회사 규모: {job.get('companySizeBand', '1000+')} 대상")
    if is_ai_venture_target(job):
        positives.append("회사군: AI 메가벤처")

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
        COLLECTION_STATS["linkedinDetailRequests"] += 1
        try:
            detail = parse_linkedin_detail(fetch(detail_url))
        except Exception as exc:
            COLLECTION_STATS["linkedinDetailFailed"] += 1
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


def make_linkedin_search_url(query, start):
    params = {
        "keywords": query,
        "location": "Tokyo, Japan",
        "f_TPR": "r2592000",
        "start": str(start),
    }
    return "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(params)


def fetch_linkedin_query(query, max_pages, rows, careers_map):
    for page in range(max_pages):
        url = make_linkedin_search_url(query, page * 25)
        COLLECTION_STATS["linkedinSearchRequests"] += 1
        try:
            cards = parse_linkedin_cards(fetch(url))
            COLLECTION_STATS["linkedinSearchSucceeded"] += 1
            if not cards:
                break
            for row in cards:
                row = add_direct_destination(row, careers_map)
                rows.setdefault(row["id"], row)
        except Exception as exc:
            COLLECTION_STATS["linkedinSearchFailed"] += 1
            print(f"[warn] LinkedIn query failed: {query} page {page + 1}: {exc}", file=sys.stderr)
            break
        time.sleep(1.0)


def collect_linkedin(max_queries, max_pages, megaventure_companies=0, rotation_slot=0):
    rows = {}
    careers_map = load_company_careers_map()
    for query in rotated_slice(LINKEDIN_QUERIES, max_queries, rotation_slot):
        fetch_linkedin_query(query, max_pages, rows, careers_map)
    mega_targets = [target for target in careers_map if is_megaventure_target(target)]
    selected_targets = rotated_slice(mega_targets, megaventure_companies, rotation_slot)
    for index, target in enumerate(selected_targets):
        company = target["name"]
        role_query = MEGAVENTURE_ROLE_QUERIES[(rotation_slot + index) % len(MEGAVENTURE_ROLE_QUERIES)]
        fetch_linkedin_query(f"{company} {role_query}", 1, rows, careers_map)
    return list(rows.values())


def absolute_url(base, href):
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urllib.parse.urljoin(base, href)


def collect_official(max_companies, rotation_slot=0):
    rows = []
    target_companies = load_target_companies()
    for target in rotated_slice(target_companies, max_companies, rotation_slot):
        company = target["name"]
        url = target["url"]
        terms = target["terms"]
        COLLECTION_STATS["officialRequests"] += 1
        try:
            page = fetch(url, timeout=6)
        except Exception as exc:
            COLLECTION_STATS["officialFailed"] += 1
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
                    "location": "Tokyo 확인 필요",
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
                    "targetCompany": company,
                    "targetCompanyType": target.get("type", ""),
                    "minCompanyEmployees": target.get("minEmployees", 0),
                    "companySizeBand": target.get("employeeBand", "1000+"),
                    "companyScaleStatus": "megaventure_500_plus" if is_megaventure_target(target) else "target_1000_plus",
                }
            )
        time.sleep(0.25)
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


def load_existing_jobs():
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

    return existing


def merge_existing(new_jobs, existing=None):
    if existing is None:
        existing = load_existing_jobs()

    merged = {job["url"]: job for job in existing}
    for job in new_jobs:
        merged[job["url"]] = job
    return list(merged.values())


def parse_seen_date(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None


def prune_stale_jobs(jobs, max_age_days):
    if max_age_days <= 0:
        return jobs
    cutoff = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=max_age_days)
    kept = []
    for job in jobs:
        if job.get("source") == "Official" and not job.get("postedDate"):
            kept.append(job)
            continue
        seen_date = parse_seen_date(job.get("lastSeenAt")) or parse_seen_date(job.get("postedDate"))
        if seen_date is None or seen_date >= cutoff:
            kept.append(job)
    return kept


def normalize_job_key(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[\s\-_‐‑‒–—―・/／｜|:：()\[\]（）【】「」『』]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def dedupe_jobs(jobs):
    deduped = {}
    for job in jobs:
        key = (
            normalize_company_name(job.get("company", "")),
            normalize_job_key(job.get("title", "")),
        )
        existing = deduped.get(key)
        if not existing:
            deduped[key] = job
            continue

        existing_rank = (
            1 if existing.get("directUrlStatus") == "verified_official" else 0,
            existing.get("score", 0),
            1 if existing.get("salaryText") else 0,
        )
        challenger_rank = (
            1 if job.get("directUrlStatus") == "verified_official" else 0,
            job.get("score", 0),
            1 if job.get("salaryText") else 0,
        )
        winner, loser = (job, existing) if challenger_rank > existing_rank else (existing, job)
        winner["reasons"] = list(dict.fromkeys((winner.get("reasons") or []) + (loser.get("reasons") or [])))
        winner["risks"] = list(dict.fromkeys((winner.get("risks") or []) + (loser.get("risks") or [])))
        if not winner.get("salaryText") and loser.get("salaryText"):
            winner["salaryText"] = loser["salaryText"]
            winner["salaryStatus"] = loser.get("salaryStatus", "listed")
        if winner.get("directUrlStatus") != "verified_official" and loser.get("directUrlStatus") == "verified_official":
            winner["directUrl"] = loser.get("directUrl", "")
            winner["directUrlStatus"] = "verified_official"
            winner["directSource"] = loser.get("directSource", "Official")
        first_seen = [value for value in [winner.get("firstSeenAt"), loser.get("firstSeenAt")] if value]
        last_seen = [value for value in [winner.get("lastSeenAt"), loser.get("lastSeenAt")] if value]
        if first_seen:
            winner["firstSeenAt"] = min(first_seen)
        if last_seen:
            winner["lastSeenAt"] = max(last_seen)
        deduped[key] = winner
    return list(deduped.values())


def write_jobs_js(jobs, collection_summary=None):
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")
    payload = json.dumps(jobs, ensure_ascii=False, indent=2)
    run = {
        "generatedAt": now,
        "mode": "collector-run",
        "recommendedPollingMinutes": 360,
        "collection": collection_summary or {},
        "notes": [
            "LinkedIn public search is paginated but rate-limited; avoid aggressive polling.",
            "Official Careers collection uses conservative keyword link scanning and may miss JavaScript-only ATS pages.",
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
    parser.add_argument("--linkedin-queries", type=int, default=12)
    parser.add_argument("--linkedin-pages", type=int, default=2)
    parser.add_argument("--linkedin-megaventure-companies", type=int, default=30)
    parser.add_argument("--linkedin-detail-limit", type=int, default=48)
    parser.add_argument("--official-companies", type=int, default=0)
    parser.add_argument("--rotation-slot", type=int, default=-1)
    parser.add_argument("--max-age-days", type=int, default=45)
    parser.add_argument("--no-linkedin", action="store_true")
    parser.add_argument("--no-official", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    rotation_slot = args.rotation_slot
    if rotation_slot < 0:
        rotation_slot = int(dt.datetime.now(dt.timezone.utc).timestamp() // (6 * 60 * 60))

    existing_jobs = load_existing_jobs()
    existing_by_url = {job.get("url"): job for job in existing_jobs if job.get("url")}
    collected_at = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")

    new_jobs = []
    if not args.no_linkedin:
        linkedin_jobs = collect_linkedin(
            args.linkedin_queries,
            args.linkedin_pages,
            args.linkedin_megaventure_companies,
            rotation_slot,
        )
        new_jobs.extend(enrich_linkedin_details(linkedin_jobs, args.linkedin_detail_limit))
    if not args.no_official:
        new_jobs.extend(collect_official(args.official_companies, rotation_slot))

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
        previous = existing_by_url.get(job.get("url"), {})
        previous_posted = previous.get("postedDate")
        job["firstSeenAt"] = (
            previous.get("firstSeenAt")
            or (f"{previous_posted}T00:00:00+09:00" if previous_posted else "")
            or collected_at
        )
        job["lastSeenAt"] = collected_at
        filtered.append(job)

    if not filtered:
        raise SystemExit("No jobs collected; keeping the previous deployment.")

    new_count = sum(1 for job in filtered if job.get("url") not in existing_by_url)
    merged = filtered if args.replace else merge_existing(filtered, existing_jobs)
    merged = dedupe_jobs(merged)
    merged = prune_stale_jobs(merged, args.max_age_days)
    merged.sort(key=lambda item: (item.get("score", 0), item.get("postedDate", "")), reverse=True)
    collection_summary = {
        **COLLECTION_STATS,
        "rotationSlot": rotation_slot,
        "collectedThisRun": len(filtered),
        "newJobs": new_count,
        "retainedJobs": max(0, len(merged) - new_count),
        "totalJobs": len(merged[:160]),
    }
    write_jobs_js(merged[:160], collection_summary)
    print(f"Wrote {len(merged[:160])} jobs to {JOBS_JS}")
    print("Collection summary: " + json.dumps(collection_summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
