#!/usr/bin/env python3
"""
pubmed_query.py — PubMed E-utilities를 통한 임상연구 문헌 검색

Citation Grounding Policy 준수: 모든 출력 인용에는 PMID가 동반된다.
LLM이 자유 생성한 인용은 본 스크립트의 출력에 포함될 수 없다.

사용법:
    python pubmed_query.py "<query>" --years 5 --max 200 --output search_log.json

환경변수:
    NCBI_API_KEY (선택, 있으면 rate limit 3→10 req/sec)
    NCBI_EMAIL  (NCBI 권고: 식별자 이메일)
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
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
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(f"{url}?{qs}", timeout=30) as r:
                return r.read()
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"PubMed request failed: {last_err}")


def esearch(query, years=5, max_results=200, types=None):
    """Boolean 쿼리 + filter → PMID list."""
    types = types or DEFAULT_TYPES
    type_filter = " OR ".join([f'"{t}"[Publication Type]' for t in types])
    full_q = f"({query}) AND ({type_filter})"
    if years:
        full_q += f' AND ("last {years} years"[PDat])'

    data = _get(f"{EUTILS}/esearch.fcgi", {
        "db": "pubmed",
        "term": full_q,
        "retmax": max_results,
        "retmode": "json"
    })
    j = json.loads(data)
    return j["esearchresult"].get("idlist", []), full_q


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
        title = (art.findtext(".//ArticleTitle") or "").strip()
        journal = (art.findtext(".//Journal/Title") or "").strip()
        year = (art.findtext(".//PubDate/Year") or "").strip()
        abstract = " ".join(t.text or "" for t in art.findall(".//AbstractText")).strip()
        doi = ""
        for elt in art.findall(".//ArticleId"):
            if elt.get("IdType") == "doi":
                doi = (elt.text or "").strip()
        authors = []
        for au in art.findall(".//Author")[:6]:
            ln = au.findtext("LastName") or ""
            init = au.findtext("Initials") or ""
            if ln:
                authors.append(f"{ln} {init}".strip())
        pub_types = [p.text for p in art.findall(".//PublicationType") if p.text]
        out.append({
            "pmid": pmid,
            "doi": doi,
            "title": title,
            "authors": authors,
            "journal": journal,
            "year": year,
            "publication_types": pub_types,
            "abstract": abstract
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="PubMed search with citation grounding")
    ap.add_argument("query", help="Boolean query (PubMed syntax)")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--types", default=None,
                    help="Comma-separated publication types")
    ap.add_argument("--output", required=True, help="Output JSON path")
    args = ap.parse_args()

    types = [t.strip() for t in args.types.split(",")] if args.types else None
    print(f"Searching PubMed: {args.query}", file=sys.stderr)

    pmids, full_q = esearch(args.query, args.years, args.max, types)
    print(f"Found {len(pmids)} PMIDs", file=sys.stderr)

    # NCBI rate limit: 3 req/s without API key, 10 with. Batch 200 per efetch is fine.
    articles = []
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i + 200]
        articles.extend(efetch(batch))
        time.sleep(0.4 if not os.environ.get("NCBI_API_KEY") else 0.1)

    log = {
        "tool": "pubmed_query.py",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_user": args.query,
        "query_full": full_q,
        "filters": {"years": args.years, "max": args.max, "types": types or DEFAULT_TYPES},
        "n_results": len(articles),
        "articles": articles
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
