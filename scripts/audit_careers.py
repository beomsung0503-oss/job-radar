import concurrent.futures
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from collect_jobs import load_target_companies  # noqa: E402


ATS_MARKERS = [
    ("greenhouse", ["greenhouse.io", "boards.greenhouse", "job-boards.greenhouse"]),
    ("lever", ["jobs.lever.co", "api.lever.co"]),
    ("ashby", ["jobs.ashbyhq.com", "api.ashbyhq.com"]),
    ("smartrecruiters", ["jobs.smartrecruiters.com", "api.smartrecruiters.com"]),
    ("workday", ["myworkdayjobs.com", "/wday/cxs/", "workdayjobs.com"]),
    ("hrmos", ["hrmos.co/pages/", "hrmos.co/jobs/"]),
    ("herp", ["herp.careers", "herp.cloud"]),
    ("talentio", ["open.talentio.com", "talentio.com"]),
    ("jobcan", ["jobcan.jp", "jobcan-ats.jp"]),
    ("jposting", ["jposting.net"]),
    ("axol", ["job.axol.jp", "mypage.3030.i-webs.jp"]),
    ("successfactors", ["career5.successfactors.eu", "career10.successfactors.com", "jobs.sap.com"]),
    ("oracle", ["oraclecloud.com/hcmui", "eeho.fa.us2.oraclecloud.com"]),
    ("icims", ["icims.com/jobs", "jobs.icims.com"]),
    ("phenom", ["phenompeople.com", "phf.tbe.taleo.net"]),
    ("avature", ["avature.net"]),
    ("amazon", ["amazon.jobs"]),
    ("google", ["google.com/about/careers"]),
]


def fetch_page(url, timeout=12):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; JobRadarCareersAudit/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(2_000_000).decode("utf-8", "replace")
        return response.geturl(), response.status, body


def detect_providers(final_url, page):
    haystack = (final_url + " " + page).lower()
    providers = []
    for provider, markers in ATS_MARKERS:
        if any(marker.lower() in haystack for marker in markers):
            providers.append(provider)
    if re.search(r'application/ld\+json[^>]*>.*?"@type"\s*:\s*"JobPosting"', page, flags=re.I | re.S):
        providers.append("jsonld")
    return list(dict.fromkeys(providers)) or ["custom"]


def extract_external_hosts(base_url, page):
    base_host = urllib.parse.urlparse(base_url).netloc.lower()
    hosts = []
    for href in re.findall(r'(?:href|src)=["\']([^"\']+)', page, flags=re.I):
        absolute = urllib.parse.urljoin(base_url, href)
        host = urllib.parse.urlparse(absolute).netloc.lower()
        if host and host != base_host and any(marker in host for _, markers in ATS_MARKERS for marker in markers if "." in marker):
            hosts.append(host)
    return list(dict.fromkeys(hosts))[:12]


def extract_provider_links(base_url, page):
    links = []
    candidates = [base_url]
    candidates.extend(re.findall(r'(?:href|src)=["\']([^"\']+)', page, flags=re.I))
    for candidate in candidates:
        absolute = urllib.parse.urljoin(base_url, candidate)
        lowered = absolute.lower()
        if any(marker.lower() in lowered for _, markers in ATS_MARKERS for marker in markers):
            links.append(absolute)
    return list(dict.fromkeys(links))[:20]


def audit_target(target):
    result = {
        "company": target["name"],
        "careersUrl": target["url"],
        "priority": target.get("priority", ""),
        "type": target.get("type", ""),
        "status": "failed",
        "finalUrl": "",
        "httpStatus": None,
        "providers": [],
        "externalAtsHosts": [],
        "providerLinks": [],
        "error": "",
    }
    try:
        final_url, status, page = fetch_page(target["url"])
        result.update(
            {
                "status": "ok",
                "finalUrl": final_url,
                "httpStatus": status,
                "providers": detect_providers(final_url, page),
                "externalAtsHosts": extract_external_hosts(final_url, page),
                "providerLinks": extract_provider_links(final_url, page),
            }
        )
    except Exception as exc:
        result["error"] = str(exc)[:240]
    return result


def main():
    targets = load_target_companies()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(audit_target, targets))

    output = ROOT / "data" / "careers_audit.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for result in results:
        for provider in result.get("providers") or ["failed"]:
            counts[provider] = counts.get(provider, 0) + 1
    print(f"Audited {len(results)} companies; {sum(item['status'] == 'ok' for item in results)} reachable")
    print(json.dumps(dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))), ensure_ascii=False))
    print(output)


if __name__ == "__main__":
    main()
