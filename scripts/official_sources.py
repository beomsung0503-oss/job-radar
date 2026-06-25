import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser


TOKYO_TERMS = ["Tokyo", "東京", "千代田", "中央区", "港区", "新宿", "渋谷", "品川", "六本木", "赤坂"]
DOMAIN_TERMS = ["Salesforce", "CRM", "Agentforce", "AI", "生成AI", "LLM", "Sales Cloud", "Service Cloud"]
ROLE_TERMS = [
    "Consultant",
    "コンサル",
    "Project Manager",
    "プロジェクトマネージャ",
    "PM",
    "PL",
    "Customer Success",
    "カスタマーサクセス",
    "Presales",
    "Pre-Sales",
    "プリセールス",
    "Implementation",
    "導入",
    "Solution",
    "DX",
    "業務改革",
    "ITコンサル",
    "IT Consultant",
    "Associate Consultant",
    "アソシエイト",
]
POTENTIAL_TERMS = [
    "ポテンシャル採用",
    "ポテンシャル",
    "第二新卒",
    "未経験可",
    "未経験歓迎",
    "未経験OK",
    "未経験から",
    "未経験",
    "育成枠",
    "キャリアチェンジ",
]
EXCLUDE_TITLE_TERMS = [
    "Engineer",
    "エンジニア",
    "Developer",
    "開発者",
    "Backend",
    "Frontend",
    "DevOps",
    "SRE",
    "Architect",
    "Administrator",
    "社内SE",
    "システムエンジニア",
]
LISTING_HINTS = [
    "career",
    "recruit",
    "job",
    "position",
    "opportunit",
    "中途",
    "キャリア",
    "採用",
    "募集職種",
    "求人",
]
ATS_JOB_HOSTS = ["hrmos.co", "herp.careers", "open.talentio.com", "myworkdayjobs.com", "jobs.ashbyhq.com"]


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self.current_href = dict(attrs).get("href")
        self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href is not None:
            text = re.sub(r"\s+", " ", " ".join(self.current_text)).strip()
            self.anchors.append((self.current_href, text))
            self.current_href = None
            self.current_text = []


def request_text(url, timeout=12, data=None, headers=None):
    parsed = urllib.parse.urlsplit(html.unescape(url))
    url = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/%:@"),
            urllib.parse.quote(urllib.parse.unquote(parsed.query), safe="=&%:/?+,-_"),
            parsed.fragment,
        )
    )
    request_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JobRadarOfficial/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
    }
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.geturl(), response.read(4_000_000).decode("utf-8", "replace")


def request_json(url, timeout=12, payload=None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    _, text = request_text(url, timeout=timeout, data=data, headers=headers)
    return json.loads(text)


def strip_tags(value):
    value = re.sub(r"<script.*?</script>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def anchors(page, base_url):
    parser = AnchorParser()
    parser.feed(page)
    rows = []
    for href, text in parser.anchors:
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        rows.append((urllib.parse.urljoin(base_url, html.unescape(href)), text))
    return rows


def contains_term(value, term):
    if term in {"PM", "PL", "AI"}:
        return bool(re.search(rf"(?:^|[^A-Za-z]){re.escape(term)}(?:$|[^A-Za-z])", value, flags=re.I))
    return term.lower() in value.lower()


def clean_listing_title(title):
    value = re.sub(r"\s+", " ", title or "").strip()
    for marker in [" 募集背景", " 職務内容", " 仕事内容", " Job Description", " About the role", " 応募資格"]:
        if marker.lower() in value.lower():
            value = value[: value.lower().index(marker.lower())]
    return value[:180].strip()


def looks_like_job_link(url, title=""):
    parsed = urllib.parse.urlparse(url)
    lowered = f"{parsed.netloc}{parsed.path}".lower()
    if any(host in parsed.netloc.lower() for host in ATS_JOB_HOSTS):
        return True
    if any(term in lowered for term in ["interview", "story", "careerpath", "group-interview", "/news", "/blog"]):
        return False
    path_hints = ["/job", "/jobs", "/career", "/careers", "/recruit", "/position", "/opening", "/requisition"]
    if any(hint in lowered for hint in path_hints):
        return True
    return any(term in title for term in ["応募", "募集職種", "採用情報", "求人"])


def title_relevant(title, target):
    title = clean_listing_title(title)
    if not title or any(term.lower() in title.lower() for term in EXCLUDE_TITLE_TERMS):
        return False
    watch_terms = target.get("terms", [])
    watch_match = any(contains_term(title, term) for term in watch_terms)
    role_match = any(contains_term(title, term) for term in ROLE_TERMS)
    domain_match = any(contains_term(title, term) for term in DOMAIN_TERMS)
    potential_match = any(contains_term(title, term) for term in POTENTIAL_TERMS)
    pure_sales = any(contains_term(title, term) for term in ["Sales", "営業", "Account Executive"])
    protected_sales = any(
        contains_term(title, term)
        for term in ["Salesforce", "Sales Cloud", "Presales", "Pre-Sales", "Customer Success", "Solution Consultant", "Consultant", "コンサル"]
    )
    if pure_sales and not protected_sales:
        return False
    return watch_match or (role_match and domain_match) or (potential_match and role_match)


def infer_location(text):
    hits = [term for term in TOKYO_TERMS if term.lower() in (text or "").lower()]
    if not hits:
        return ""
    if "Tokyo" in hits or "東京" in hits:
        return "Tokyo, Japan"
    return "Tokyo, Japan (본문 확인)"


def extract_salary(text):
    normalized = re.sub(r"\s+", " ", text or "")
    patterns = [
        r"(?:想定年収|予定年収|年収|給与)\s*[:：]?\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*[~〜～\-－]\s*[0-9,]+(?:\.[0-9]+)?\s*(?:万|万円)?\s*円?",
        r"(?:Annual salary|Salary|Compensation)\s*[:：]?\s*(?:JPY|¥|円)?\s*[0-9,]+(?:\.[0-9]+)?\s*[~〜～\-－]\s*(?:JPY|¥|円)?\s*[0-9,]+(?:\.[0-9]+)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.I)
        if match:
            return match.group(0).strip(" 、。")
    return ""


def jsonld_nodes(page):
    nodes = []
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page or "",
        flags=re.I | re.S,
    )

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            node_type = value.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "JobPosting" in types:
                nodes.append(value)
            for key in ["@graph", "itemListElement"]:
                if key in value:
                    walk(value[key])

    for script in scripts:
        try:
            walk(json.loads(html.unescape(script).strip()))
        except (json.JSONDecodeError, TypeError):
            continue
    return nodes


def jsonld_location(node):
    locations = node.get("jobLocation") or []
    if not isinstance(locations, list):
        locations = [locations]
    parts = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address") or {}
        if isinstance(address, dict):
            parts.extend(
                str(address.get(key, ""))
                for key in ["streetAddress", "addressLocality", "addressRegion", "addressCountry"]
                if address.get(key)
            )
    return " ".join(dict.fromkeys(parts))


def meta_content(page, property_name):
    patterns = [
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(property_name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(property_name)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, page or "", flags=re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def parse_detail_page(page, url, fallback_title=""):
    nodes = jsonld_nodes(page)
    node = nodes[0] if nodes else {}
    title = str(node.get("title") or "")
    if not title:
        title = meta_content(page, "og:title")
    if not title:
        match = re.search(r"<h1[^>]*>(.*?)</h1>", page or "", flags=re.I | re.S)
        title = strip_tags(match.group(1)) if match else fallback_title
    description = strip_tags(str(node.get("description") or ""))
    if not description:
        main = re.search(r"<main[^>]*>(.*?)</main>", page or "", flags=re.I | re.S)
        description = strip_tags(main.group(1) if main else page)
    location = jsonld_location(node) or infer_location(description)
    direct_url = str(node.get("url") or url)
    return {
        "title": title or fallback_title,
        "description": description[:6000],
        "location": location,
        "postedDate": str(node.get("datePosted") or "")[:10],
        "employmentType": str(node.get("employmentType") or ""),
        "salaryText": extract_salary(description),
        "url": urllib.parse.urljoin(url, direct_url),
    }


def make_job(target, detail, provider):
    url = detail.get("url", "")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    salary = detail.get("salaryText", "")
    return {
        "id": f"official-{provider}-{digest}",
        "source": "Official",
        "sourceQuality": "official",
        "title": detail.get("title", "")[:180],
        "company": target["name"],
        "location": detail.get("location", "") or "勤務地要確認",
        "postedDate": detail.get("postedDate", ""),
        "salaryText": salary,
        "salaryStatus": "listed" if salary else "not_listed",
        "employmentType": detail.get("employmentType", ""),
        "seniority": "",
        "jobFunction": "",
        "url": url,
        "directUrl": url,
        "directUrlStatus": "verified_official",
        "directSearchUrl": "",
        "status": "open",
        "fit": "backup",
        "score": 0,
        "descriptionText": detail.get("description", "")[:6000],
        "reasons": [f"공식 {provider} 공고에서 직접 수집"],
        "risks": [],
        "directSource": f"{provider} official",
        "targetCompany": target["name"],
        "targetCompanyType": target.get("type", ""),
        "minCompanyEmployees": target.get("minEmployees", 0),
        "companySizeBand": target.get("employeeBand", "1000+"),
        "companyScaleStatus": "megaventure_500_plus" if "megaventure" in target.get("type", "") else "target_1000_plus",
    }


def fetch_candidate(target, title, url, provider, seed=None):
    title = clean_listing_title(title)
    if not title_relevant(title, target):
        return None
    detail = dict(seed or {})
    detail.setdefault("title", title)
    detail.setdefault("url", url)
    page = ""
    try:
        _, page = request_text(url)
        parsed = parse_detail_page(page, url, title)
        for key, value in parsed.items():
            if value:
                detail[key] = value
    except Exception:
        pass
    if provider == "Careers":
        path = urllib.parse.urlparse(url).path.lower()
        strong_path = any(
            hint in path
            for hint in ["/jobs/", "/job/", "/job-categories/", "/offers/", "/positions/", "/requisitions/"]
        )
        apply_signal = bool(re.search(r"応募(?:する|フォーム|はこちら)|エントリー|apply\s+now|jobposting", page, flags=re.I))
        if not jsonld_nodes(page) and not strong_path and not apply_signal:
            return None
    listed_location = detail.get("location", "")
    if listed_location and listed_location != "勤務地要確認" and not infer_location(listed_location):
        return None
    combined = " ".join([detail.get("title", ""), detail.get("location", ""), detail.get("description", "")])
    if not infer_location(combined):
        return None
    detail["location"] = detail.get("location") or infer_location(combined)
    if not title_relevant(detail.get("title", ""), target):
        return None
    return make_job(target, detail, provider)


def collect_hrmos(target, provider_links):
    rows = []
    orgs = []
    for link in provider_links:
        match = re.search(r"hrmos\.co/pages/([^/?#]+)", link, flags=re.I)
        if match:
            orgs.append(match.group(1))
    for org in dict.fromkeys(orgs):
        board_url = f"https://hrmos.co/pages/{org}/jobs"
        _, page = request_text(board_url)
        for link, title in anchors(page, board_url):
            if not re.search(rf"hrmos\.co/pages/{re.escape(org)}/jobs/[^/?#]+/?$", link, flags=re.I):
                continue
            job = fetch_candidate(target, title, link, "HRMOS")
            if job:
                rows.append(job)
    return rows


def collect_herp(target, provider_links):
    rows = []
    orgs = []
    for link in provider_links:
        match = re.search(r"herp\.careers/v1/([^/?#]+)", link, flags=re.I)
        if match:
            orgs.append(match.group(1))
    for org in dict.fromkeys(orgs):
        board_url = f"https://herp.careers/v1/{org}"
        _, page = request_text(board_url)
        for link, title in anchors(page, board_url):
            if not re.search(rf"herp\.careers/v1/{re.escape(org)}/[^/?#]+/?$", link, flags=re.I):
                continue
            job = fetch_candidate(target, title, link, "HERP")
            if job:
                rows.append(job)
    return rows


def talentio_entries(page):
    match = re.search(r'data-react-props="([^"]+)"', page or "", flags=re.I)
    if not match:
        return []
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return []
    entries = []

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            if value.get("publishedUrl") and value.get("name"):
                entries.append((str(value["publishedUrl"]), str(value["name"])))
            for child in value.values():
                walk(child)

    walk(payload)
    return list(dict.fromkeys(entries))


def collect_talentio(target, provider_links):
    rows = []
    pages = [link for link in provider_links if "open.talentio.com" in link]
    for url in dict.fromkeys(pages):
        try:
            _, page = request_text(url)
        except Exception:
            continue
        entries = talentio_entries(page)
        if not entries and "/requisitions/detail/" in url:
            detail = parse_detail_page(page, url)
            entries = [(url, detail.get("title", ""))]
        for link, title in entries:
            job = fetch_candidate(target, title, link, "Talentio")
            if job:
                rows.append(job)
    return rows


def collect_ashby(target, provider_links):
    rows = []
    orgs = []
    for link in provider_links:
        match = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", link, flags=re.I)
        if match:
            orgs.append(match.group(1))
    for org in dict.fromkeys(orgs):
        payload = request_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
        for item in payload.get("jobs", []):
            title = item.get("title", "")
            url = item.get("jobUrl", "")
            seed = {
                "title": title,
                "url": url,
                "location": item.get("location", ""),
                "description": strip_tags(item.get("descriptionHtml", "")),
                "employmentType": item.get("employmentType", ""),
            }
            job = fetch_candidate(target, title, url, "Ashby", seed)
            if job:
                rows.append(job)
    return rows


def workday_boards(provider_links):
    boards = []
    for link in provider_links:
        parsed = urllib.parse.urlparse(html.unescape(link))
        if "myworkdayjobs.com" not in parsed.netloc.lower():
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if parts and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]):
            parts = parts[1:]
        if not parts:
            continue
        site = parts[0]
        tenant = parsed.netloc.split(".")[0]
        boards.append((parsed.scheme or "https", parsed.netloc, tenant, site))
    return list(dict.fromkeys(boards))


def collect_workday(target, provider_links):
    rows = []
    search_terms = list(
        dict.fromkeys(
            target.get("terms", [])
            + ["Salesforce", "CRM", "Customer Success", "ポテンシャル採用", "第二新卒", "未経験可"]
        )
    )[:8]
    for scheme, host, tenant, site in workday_boards(provider_links):
        api_root = f"{scheme}://{host}/wday/cxs/{tenant}/{site}"
        postings = {}
        for term in search_terms:
            try:
                payload = request_json(
                    api_root + "/jobs",
                    payload={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term},
                )
            except Exception:
                continue
            for item in payload.get("jobPostings", []):
                path = item.get("externalPath", "")
                if path:
                    postings[path] = item
        for path, item in postings.items():
            title = item.get("title", "")
            if not title_relevant(title, target):
                continue
            detail_url = api_root + path
            public_url = f"{scheme}://{host}/{site}{path}"
            seed = {
                "title": title,
                "url": public_url,
                "location": item.get("locationsText", ""),
                "postedDate": item.get("postedOn", ""),
            }
            try:
                detail_payload = request_json(detail_url)
                info = detail_payload.get("jobPostingInfo", {})
                seed.update(
                    {
                        "title": info.get("title") or seed["title"],
                        "location": info.get("location") or seed["location"],
                        "description": strip_tags(info.get("jobDescription", "")),
                        "employmentType": info.get("timeType", ""),
                        "postedDate": str(info.get("startDate") or seed["postedDate"])[:10],
                        "salaryText": extract_salary(info.get("jobDescription", "")),
                        "url": info.get("externalUrl") or public_url,
                    }
                )
            except Exception:
                pass
            combined = " ".join([seed.get("location", ""), seed.get("description", "")])
            if not infer_location(combined):
                continue
            seed["location"] = seed.get("location") or infer_location(combined)
            rows.append(make_job(target, seed, "Workday"))
    return rows


def collect_jsonld(target, page, base_url):
    rows = []
    for node in jsonld_nodes(page):
        title = str(node.get("title") or "")
        if not title_relevant(title, target):
            continue
        detail = {
            "title": title,
            "url": urllib.parse.urljoin(base_url, str(node.get("url") or base_url)),
            "location": jsonld_location(node),
            "postedDate": str(node.get("datePosted") or "")[:10],
            "employmentType": str(node.get("employmentType") or ""),
            "description": strip_tags(str(node.get("description") or ""))[:6000],
        }
        detail["salaryText"] = extract_salary(detail["description"])
        if infer_location(" ".join([detail["location"], detail["description"]])):
            rows.append(make_job(target, detail, "JSON-LD"))
    return rows


def collect_generic(target, start_url):
    rows = []
    visited = set()
    queue = [start_url]
    listing_pages_added = 0
    while queue and len(visited) < 4:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        final_url, page = request_text(url)
        rows.extend(collect_jsonld(target, page, final_url))
        for link, title in anchors(page, final_url):
            if title_relevant(title, target) and looks_like_job_link(link, title):
                job = fetch_candidate(target, title, link, "Careers")
                if job:
                    rows.append(job)
                continue
            same_host = urllib.parse.urlparse(link).netloc == urllib.parse.urlparse(final_url).netloc
            hint_text = f"{title} {urllib.parse.urlparse(link).path}".lower()
            if same_host and listing_pages_added < 3 and any(hint.lower() in hint_text for hint in LISTING_HINTS):
                queue.append(link)
                listing_pages_added += 1
    return rows


def collect_official_jobs(target, registry=None):
    registry = registry or {}
    providers = registry.get("providers") or ["custom"]
    provider_links = list(registry.get("providerLinks") or [])
    start_url = registry.get("finalUrl") or target["url"]
    if start_url not in provider_links:
        provider_links.append(start_url)
    rows = []
    errors = []
    adapters = {
        "hrmos": collect_hrmos,
        "herp": collect_herp,
        "talentio": collect_talentio,
        "ashby": collect_ashby,
        "workday": collect_workday,
    }
    for provider in providers:
        adapter = adapters.get(provider)
        if not adapter:
            continue
        try:
            rows.extend(adapter(target, provider_links))
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    try:
        rows.extend(collect_generic(target, start_url))
    except Exception as exc:
        errors.append(f"generic: {exc}")
    deduped = {}
    for row in rows:
        deduped[row["url"]] = row
    return {"jobs": list(deduped.values()), "errors": errors, "providers": providers}
