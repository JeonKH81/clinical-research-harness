#!/usr/bin/env python3
"""
verify_citations.py — Citation Grounding 강제 (인용 환각 자동 탐지)

생성된 문서(research_opportunities.md, literature_review.md, 연구계획서 초안 등)에
포함된 모든 PMID/DOI를 PubMed esummary / Crossref로 실제 resolve하여
*존재하지 않는(환각) 인용*을 탐지한다. Citation Grounding 정책의 코드 레벨 강제.

근거: LLM의 의학 인용 환각률 30–50% (Bhattacharyya 2023, Chelli JMIR 2024).
이 스크립트는 인용의 *존재*를 보장한다 (논문이 본문 주장을 실제로 지지하는지는 별도 검토).

사용법:
    python verify_citations.py FILE [FILE ...] [--json report.json] [--strict]

    # search_log.json 의 PMID 화이트리스트와 대조 (생성문에 search_log 밖 PMID가 있으면 의심)
    python verify_citations.py research_opportunities.md --search-log search_log.json

종료 코드:
    0  모든 인용 검증 통과 (또는 인용 없음)
    1  검증 실패 인용 존재 (환각 의심) — --strict 시 거절 게이트로 사용

환경변수:
    NCBI_API_KEY (선택), NCBI_EMAIL (NCBI/Crossref 식별 권고)
"""

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF = "https://api.crossref.org/works"


def _ssl_context():
    """SSL 컨텍스트. HARNESS_INSECURE_SSL=1 이면 검증 비활성화(사내 SSL 가로채기 환경 옵트인)."""
    if os.environ.get("HARNESS_INSECURE_SSL", "").lower() in ("1", "true", "yes"):
        print("[WARN] HARNESS_INSECURE_SSL — TLS 인증서 검증 비활성화됨 (보안 약화).",
              file=sys.stderr)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None  # 기본: 시스템 신뢰 저장소 / SSL_CERT_FILE 사용


def _is_ssl_cert_error(exc):
    """urllib이 URLError로 감싸도 SSL 인증서 오류를 탐지."""
    if isinstance(exc, ssl.SSLError):
        return True
    if isinstance(getattr(exc, "reason", None), ssl.SSLError):
        return True
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


_SSL_HINT = (
    "TLS 인증서 검증 실패 (사내/프록시 SSL 가로채기 가능성). 해결:\n"
    "  1) 회사 루트 CA로  export SSL_CERT_FILE=/path/to/corp-ca.pem , 또는\n"
    "  2) export SSL_CERT_FILE=$(python3 -m certifi) , 또는\n"
    "  3) (검증 생략, 보안 약화) export HARNESS_INSECURE_SSL=1"
)

# [PMID: 12345678] / PMID 12345678 / pmid:12345678
PMID_RE = re.compile(r"PMID[:\s]*([0-9]{1,9})", re.IGNORECASE)
# [DOI: 10.xxxx/...] — 닫는 괄호/대괄호/공백 전까지
DOI_RE = re.compile(r"DOI[:\s]*\s*(10\.\d{4,9}/[^\s\]\)<>\"]+)", re.IGNORECASE)


def _email():
    return os.environ.get("NCBI_EMAIL", "harness@example.com")


def _get(url, params=None, headers=None, retries=3):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    ctx = _ssl_context()
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            # 404 등은 재시도 없이 그대로 반환 (존재하지 않음 = 검증 결과)
            return e.code, b""
        except Exception as e:
            if _is_ssl_cert_error(e):
                raise RuntimeError(f"{_SSL_HINT}\n  원본 오류: {e}") from e
            last_err = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"request failed: {last_err}")


def extract_citations(text):
    """문서 텍스트에서 (kind, id) 인용 추출 (중복 제거, 등장 순서 유지)."""
    found = []
    seen = set()
    for m in PMID_RE.finditer(text):
        key = ("pmid", m.group(1))
        if key not in seen:
            seen.add(key)
            found.append(key)
    for m in DOI_RE.finditer(text):
        doi = m.group(1).rstrip(".,;)")
        key = ("doi", doi)
        if key not in seen:
            seen.add(key)
            found.append(key)
    return found


def verify_pmid(pmid):
    """PubMed esummary로 PMID 존재 확인."""
    params = {"db": "pubmed", "id": pmid, "retmode": "json",
              "tool": "clinical-research-harness", "email": _email()}
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    status, body = _get(f"{EUTILS}/esummary.fcgi", params)
    if status != 200 or not body:
        return False, f"HTTP {status}"
    try:
        j = json.loads(body)
    except json.JSONDecodeError:
        return False, "invalid JSON"
    res = j.get("result", {})
    rec = res.get(str(pmid))
    if not rec:
        return False, "not found"
    if "error" in rec:
        return False, str(rec["error"])
    title = rec.get("title", "")
    return True, title[:120]


def verify_doi(doi):
    """Crossref로 DOI 존재 확인."""
    ua = f"clinical-research-harness (mailto:{_email()})"
    url = f"{CROSSREF}/{urllib.parse.quote(doi)}"
    status, body = _get(url, headers={"User-Agent": ua})
    if status == 200 and body:
        try:
            j = json.loads(body)
            title = (j.get("message", {}).get("title") or [""])[0]
            return True, title[:120]
        except json.JSONDecodeError:
            return True, ""
    return False, f"HTTP {status}"


def load_search_log_ids(path):
    """search_log.json에서 도구 검색으로 확보한 PMID/DOI 화이트리스트."""
    pmids, dois = set(), set()
    try:
        with open(path) as f:
            log = json.load(f)
        for a in log.get("articles", []):
            if a.get("pmid"):
                pmids.add(str(a["pmid"]))
            if a.get("doi"):
                dois.add(a["doi"].lower())
    except (OSError, json.JSONDecodeError) as e:
        print(f"[WARN] search_log 읽기 실패 ({path}): {e}", file=sys.stderr)
    return pmids, dois


def main():
    ap = argparse.ArgumentParser(description="Citation grounding verifier (인용 환각 탐지)")
    ap.add_argument("files", nargs="+", help="검증할 문서 (.md/.txt 등)")
    ap.add_argument("--search-log", default=None,
                    help="search_log.json — 도구 검색 화이트리스트와 대조")
    ap.add_argument("--json", default=None, help="검증 리포트 JSON 출력 경로")
    ap.add_argument("--strict", action="store_true",
                    help="search_log 밖 인용도 실패로 간주 (엄격 게이트)")
    args = ap.parse_args()

    wl_pmids, wl_dois = (set(), set())
    if args.search_log:
        wl_pmids, wl_dois = load_search_log_ids(args.search_log)

    results = []
    n_fail = 0
    cache = {}
    for path in args.files:
        try:
            with open(path) as f:
                text = f.read()
        except OSError as e:
            print(f"[WARN] 파일 읽기 실패: {path} ({e})", file=sys.stderr)
            continue
        for kind, cid in extract_citations(text):
            ckey = (kind, cid.lower() if kind == "doi" else cid)
            if ckey in cache:
                ok, note = cache[ckey]
            else:
                if kind == "pmid":
                    ok, note = verify_pmid(cid)
                else:
                    ok, note = verify_doi(cid)
                cache[ckey] = (ok, note)
                time.sleep(0.12 if os.environ.get("NCBI_API_KEY") else 0.34)

            in_whitelist = None
            if args.search_log:
                in_whitelist = (cid in wl_pmids) if kind == "pmid" \
                    else (cid.lower() in wl_dois)

            status = "verified" if ok else "FAILED (resolve 실패 — 환각 의심)"
            if ok and args.search_log and in_whitelist is False:
                status = "verified_but_not_in_search_log (사용자 입력 인용?)"
                if args.strict:
                    status = "FAILED (search_log 밖 인용 — strict)"

            failed = status.startswith("FAILED")
            if failed:
                n_fail += 1
            results.append({
                "file": path, "kind": kind, "id": cid,
                "resolved": ok, "in_search_log": in_whitelist,
                "status": status, "note": note,
            })
            mark = "✓" if not failed else "✗"
            print(f"  {mark} [{kind.upper()}: {cid}] {status} — {note}", file=sys.stderr)

    total = len(results)
    print(f"\n[CITATION CHECK] {total}건 검사, {n_fail}건 실패", file=sys.stderr)

    report = {
        "tool": "verify_citations.py",
        "version": "1.0",
        "files": args.files,
        "search_log": args.search_log,
        "strict": args.strict,
        "n_citations": total,
        "n_failed": n_fail,
        "citations": results,
    }
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"리포트: {args.json}", file=sys.stderr)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        # 네트워크/SSL 등 환경 오류 — exit 2 (인용 실패[exit 1]와 구분)
        print(f"[ENV ERROR] {e}", file=sys.stderr)
        sys.exit(2)
