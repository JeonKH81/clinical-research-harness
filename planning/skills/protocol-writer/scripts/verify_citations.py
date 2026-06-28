#!/usr/bin/env python3
"""
verify_citations.py — Citation Grounding 비타협 검증.

연구계획서가 사용한 모든 참고문헌(protocol_content.resolved.json의 references)이
Phase 1 search_log.json에 PMID 또는 DOI로 실재하는지 대조한다.
search_log에 없는 인용 = hallucination 후보 → exit code 2로 차단 신호.

또한 본문(background)의 [n] in-text citation 번호가 references 범위 내인지 점검한다.

사용:
  python verify_citations.py --resolved phase3_protocol/protocol_content.resolved.json \
    --refs phase1_lit/search_log.json
출력: stdout JSON, exit 0(통과)/2(차단)/1(입력오류)
"""
import argparse, json, os, re, sys

def load(p):
    if not p or not os.path.exists(p): return None
    return json.load(open(p,encoding="utf-8"))

def index_searchlog(refs):
    pmids,dois=set(),set()
    if not refs: return pmids,dois
    items=refs.get("results") if isinstance(refs,dict) else refs
    if not isinstance(items,list): return pmids,dois
    for it in items:
        if not isinstance(it,dict): continue
        if it.get("pmid"): pmids.add(str(it["pmid"]).strip())
        if it.get("doi"): dois.add(str(it["doi"]).strip().lower())
    return pmids,dois

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--resolved",required=True)
    ap.add_argument("--refs",required=True)
    a=ap.parse_args()
    content=load(a.resolved); refs=load(a.refs)
    if content is None: print(json.dumps({"error":f"resolved 없음: {a.resolved}"},ensure_ascii=False)); sys.exit(1)
    pmids,dois=index_searchlog(refs)
    used=content.get("references",[]) or []
    grounded,ungrounded=[],[]
    for r in used:
        pmid=str(r.get("pmid") or "").strip(); doi=str(r.get("doi") or "").strip().lower()
        ok=(pmid and pmid in pmids) or (doi and doi in dois)
        rec={"n":r.get("n"),"text":(r.get("text") or "")[:80],"pmid":pmid,"doi":doi}
        (grounded if ok else ungrounded).append(rec)
    # in-text [n] 점검
    bg=str(content.get("background") or "")
    intext=sorted(set(int(x) for x in re.findall(r"\[(\d+)\]",bg)))
    max_ref=max([r.get("n",0) for r in used],default=0)
    dangling=[n for n in intext if n>max_ref or n<1]
    result={
        "grounded_count":len(grounded),
        "ungrounded_count":len(ungrounded),
        "ungrounded":ungrounded,
        "intext_citations":intext,
        "dangling_intext":dangling,
        "verdict":"PASS" if (not ungrounded and not dangling) else "BLOCK",
    }
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result["verdict"]=="PASS" else 2)

if __name__=="__main__":
    main()
