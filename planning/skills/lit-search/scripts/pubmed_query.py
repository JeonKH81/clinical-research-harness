#!/usr/bin/env python3
"""
pubmed_query.py — PubMed E-utilities를 통한 임상연구 문헌 검색

Citation Grounding Policy 준수: 모든 출력 인용에는 도구가 반환한 PMID가 동반된다.
LLM이 자유 생성한 인용은 본 스크립트의 출력에 포함될 수 없다.
(생성된 .md 문서의 인용 검증은 verify_citations.py 참조)

사용법:
    python pubmed_query.py "<query>" --years 5 --max 200 --output search_log.json

    # 출판유형 필터 비활성화 (관찰연구·코호트 등 폭넓은 검색 — B1 replication / B3 RWE / A population)
    python pubmed_query.py "<query>" --types none --output search_log.json

    # 관찰연구 포함 검색
    python pubmed_query.py "<query>" --types "Observational Study,Cohort Studies" --output search_log.json

환경변수:
    NCBI_API_KEY (선택, 있으면 rate limit 3→10 req/sec)
    NCBI_EMAIL  (NCBI 권고: 식별자 이메일)
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


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
    "  1) export SSL_CERT_FILE=/path/to/corp-ca.pem , 또는\n"
    "  2) export SSL_CERT_FILE=$(python3 -m certifi) , 또는\n"
    "  3) (검증 생략, 보안 약화) export HARNESS_INSECURE_SSL=1"
)
# 기본은 근거수준 높은 유형 우선 (Recency × Quality). 단 후향 코호트 선행연구
# (B1 replication, B3 RWE)를 찾으려면 --types none 으로 필터를 끄거나
# "Observational Study,Cohort Studies" 를 명시해야 한다.
DEFAULT_TYPES = ["Systematic Review", "Meta-Analysis",
                 "Randomized Controlled Trial", "Clinical Trial"]


def _get(url, params, retries=3):
    """NCBI rate-limit aware GET."""
    api_key = os.environ.get("NCBI_API_KEY")
    email = os.environ.get("NCBI_EMAIL", "harness@example.com")
    params = {**params, "tool": "clinical-research-harness", "email": email}
    if api_key:
        params["api_key"] = api_key
    qs = urllib.parse.urlencode(params)
    ctx = _ssl_context()
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(f"{url}?{qs}", timeout=30, context=ctx) as r:
                return r.read()
        except Exception as e:
            if _is_ssl_cert_error(e):
                raise RuntimeError(f"{_SSL_HINT}\n  원본 오류: {e}") from e
            last_err = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"PubMed request failed: {last_err}")


def esearch(query, years=5, max_results=200, types=None, sort="relevance",
            no_type_filter=False):
    """Boolean 쿼리 + filter → (PMID list, full_query).

    no_type_filter=True 또는 types가 빈 리스트면 출판유형 필터를 적용하지 않는다.
    """
    full_q = f"({query})"
    if not no_type_filter:
        types = types or DEFAULT_TYPES
        if types:
            type_filter = " OR ".join([f'"{t}"[Publication Type]' for t in types])
            full_q += f" AND ({type_filter})"
    if years:
        full_q += f' AND ("last {years} years"[PDat])'

    params = {
        "db": "pubmed",
        "term": full_q,
        "retmax": max_results,
        "retmode": "json",
    }
    if sort and sort != "default":
        params["sort"] = sort  # 재현성: 정렬 기준 고정 (default relevance)

    data = _get(f"{EUTILS}/esearch.fcgi", params)
    j = json.loads(data)
    res = j.get("esearchresult", {})

    # PubMed가 쿼리 오류를 ERROR로 반환하는 경우 조용히 삼키지 않는다.
    if "ERROR" in res:
        raise RuntimeError(f"PubMed esearch error: {res['ERROR']}")
    errlist = res.get("errorlist") or {}
    if errlist.get("phrasesnotfound") or errlist.get("fieldsnotfound"):
        print(f"[WARN] PubMed errorlist: {errlist}", file=sys.stderr)

    idlist = res.get("idlist", [])
    try:
        count = int(res.get("count", len(idlist)))
    except (TypeError, ValueError):
        count = len(idlist)
    if count > max_results:
        print(f"[WARN] {count} results matched but capped at --max {max_results}. "
              f"재현성을 위해 쿼리를 더 좁히거나 --max 를 늘리십시오.", file=sys.stderr)
    return idlist, full_q, count


def _extract_doi(art):
    """ArticleId 와 ELocationID 양쪽에서 DOI 추출."""
    for elt in art.findall(".//ArticleIdList/ArticleId"):
        if elt.get("IdType") == "doi" and (elt.text or "").strip():
            return elt.text.strip()
    for elt in art.findall(".//ELocationID"):
        if elt.get("EIdType") == "doi" and (elt.text or "").strip():
            return elt.text.strip()
    return ""


def _extract_abstract(art):
    """구조화 라벨(BACKGROUND/METHODS…)과 inline 마크업(<i>,<sup>)을 보존하며 초록 추출."""
    parts = []
    for ab in art.findall(".//Abstract/AbstractText"):
        text = "".join(ab.itertext()).strip()
        if not text:
            continue
        label = ab.get("Label")
        parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts)


def _extract_authors(art, limit=6):
    authors = []
    for au in art.findall(".//AuthorList/Author")[:limit]:
        ln = au.findtext("LastName")
        if ln:
            init = au.findtext("Initials") or ""
            authors.append(f"{ln} {init}".strip())
        else:
            coll = au.findtext("CollectiveName")
            if coll:
                authors.append(coll.strip())
    return authors


def efetch(pmids):
    """PMID list → 메타데이터 (title, authors, journal, year, abstract, DOI)."""
    if not pmids:
        return []
    data = _get(f"{EUTILS}/efetch.fcgi", {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    })
    root = ET.fromstring(data)
    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid = (art.findtext(".//PMID") or "").strip()
        title = "".join(art.find(".//ArticleTitle").itertext()).strip() \
            if art.find(".//ArticleTitle") is not None else ""
        journal = (art.findtext(".//Journal/ISOAbbreviation")
                   or art.findtext(".//Journal/Title") or "").strip()
        year = (art.findtext(".//JournalIssue/PubDate/Year")
                or art.findtext(".//PubDate/Year") or "").strip()
        pub_types = [p.text for p in art.findall(".//PublicationType") if p.text]
        out.append({
            "pmid": pmid,
            "doi": _extract_doi(art),
            "title": title,
            "authors": _extract_authors(art),
            "journal": journal,
            "year": year,
            "publication_types": pub_types,
            "abstract": _extract_abstract(art)
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="PubMed search with citation grounding")
    ap.add_argument("query", help="Boolean query (PubMed syntax)")
    ap.add_argument("--years", type=int, default=5, help="0 이면 연도 필터 없음")
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--types", default=None,
                    help="Comma-separated publication types. 'none' 이면 출판유형 필터 비활성화 "
                         "(관찰연구·코호트 포함 폭넓은 검색)")
    ap.add_argument("--sort", default="relevance",
                    help="esearch 정렬 (relevance|pub_date|…). 재현성을 위해 고정 권장")
    ap.add_argument("--output", required=True, help="Output JSON path")
    args = ap.parse_args()

    no_type_filter = False
    types = None
    if args.types:
        if args.types.strip().lower() in ("none", "all", "off"):
            no_type_filter = True
        else:
            types = [t.strip() for t in args.types.split(",") if t.strip()]

    print(f"Searching PubMed: {args.query}", file=sys.stderr)
    pmids, full_q, count = esearch(args.query, args.years, args.max, types,
                                   sort=args.sort, no_type_filter=no_type_filter)
    print(f"Found {len(pmids)} PMIDs (total matched: {count})", file=sys.stderr)

    # NCBI rate limit: 3 req/s without API key, 10 with. Batch 200 per efetch.
    articles = []
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i + 200]
        articles.extend(efetch(batch))
        time.sleep(0.4 if not os.environ.get("NCBI_API_KEY") else 0.1)

    log = {
        "tool": "pubmed_query.py",
        "version": "1.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_user": args.query,
        "query_full": full_q,
        "filters": {
            "years": args.years,
            "max": args.max,
            "sort": args.sort,
            "types": ("none (disabled)" if no_type_filter else (types or DEFAULT_TYPES)),
        },
        "n_total_matched": count,
        "n_results": len(articles),
        "articles": articles
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"[ENV ERROR] {e}", file=sys.stderr)
        sys.exit(2)
