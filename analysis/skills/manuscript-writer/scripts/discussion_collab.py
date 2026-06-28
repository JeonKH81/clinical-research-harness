#!/usr/bin/env python3
"""
discussion_collab.py — Discussion 이중 저자(Claude + Codex) 협업의 Codex 측 헬퍼

Phase 6 manuscript-writer의 Discussion 작성을 Claude·Codex 공동작업으로 수행한다.
이 스크립트는 *Codex 측 호출과 가용성 감지*만 결정론적으로 책임진다.
Claude 측 초안·검토·최종 종합은 manuscript-writer agent(LLM)가 직접 수행한다.

협업 흐름 (agent가 오케스트레이션):
  [A] 독립 초안     A1 Claude→claude_v1 (agent)   ‖  A2 codex-draft →codex_v1 (이 스크립트)
  [B] 교차 검토     B1 Claude reviews codex_v1 (agent) ‖ B2 codex-review →review_codex_on_claude (이 스크립트)
  [C] 종합          Claude가 4개 산출물 → discussion_final.md (agent)
  [fallback] probe 실패 시 A2·B2 생략 → Claude 단독 종합

비타협 정책 (두 저자 공통, Codex 프롬프트에 강제 주입):
  - Citation Grounding: 패킷의 허용 인용(PMID/DOI) 외 새 인용 생성 금지
  - PHI 비전송: 패킷에는 집계 통계만 (개별 환자 row 없음). 이 스크립트는 패킷을 그대로 전달
  - 인과 과대해석 금지(관찰연구), effect size+95% CI 보고 유지

서브커맨드:
  probe                                       Codex 사용 가능 여부 (exit 0=가능, 1=불가)
  codex-draft  --packet F --out F             Codex가 Discussion 초안 작성
  codex-review --draft F --packet F --out F   Codex가 주어진 초안을 교차 검토

종료 코드:
  0  성공 (probe: 사용 가능)
  1  Codex 사용 불가 (probe 실패 / 미설치 / 미인증) — agent는 단독 모드로 fallback
  2  실행 오류 (타임아웃·예기치 못한 실패)

사용법:
  python discussion_collab.py probe
  python discussion_collab.py codex-draft  --packet discussion_packet.md --out discussion_codex_v1.md
  python discussion_collab.py codex-review --draft discussion_claude_v1.md \
         --packet discussion_packet.md --out review_codex_on_claude.md
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

# Codex exec 비대화 호출 기본 플래그.
# - read-only 샌드박스: Codex는 파일을 수정하지 않고 최종 메시지만 -o 로 기록
# - --skip-git-repo-check: workspace가 git repo가 아니어도 동작
# - --color never: 출력 파싱/로그 안정성
CODEX_BASE = ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never"]
DEFAULT_TIMEOUT = 420  # 초

# ---- 두 저자 공통 비타협 규칙 (Codex 프롬프트 머리말) ----
GROUNDING_RULES = """\
다음 규칙을 반드시 지키십시오 (위반 시 출력은 폐기됩니다):
1. 인용은 아래 입력 패킷의 '허용 인용 목록(PMID/DOI)'에 있는 것만 사용합니다. 새 인용을 만들어내지 마십시오.
2. 결과 수치(effect size, 95% CI 등)는 패킷에 주어진 값만 사용하고 새로 만들지 마십시오. p-value 단독 보고 금지.
3. 이것은 후향적 관찰연구입니다. 인과(causal) 표현을 과도하게 쓰지 말고 연관(association) 수준으로 기술하십시오.
4. 환자 개인정보(PHI)는 패킷에 없습니다. 개별 환자 수준 서술을 만들지 마십시오.
5. 출력은 학술지 Discussion 섹션 본문(영어, Markdown)만 작성합니다. 메타 설명·사족 없이 본문만.
"""

DRAFT_INSTRUCTION = """\
당신은 심혈관 임상연구 논문의 공동 저자입니다. 아래 입력 패킷(주요 결과·선행연구·연구 gap·한계 4항목)을
근거로 학술지 투고용 **Discussion 섹션** 초안을 작성하십시오.

구성:
- 1문단: 핵심 결과 요약 (effect size + 95% CI를 본문에 자연스럽게)
- 1-2문단: 선행연구와의 비교 (패킷의 허용 인용만 사용)
- 1문단: 임상적 함의 (단, 단정적 임상 권고는 피하고 신중히)
- 1문단: 한계 (패킷의 Limitations 4항목 — 선택편향·측정편향·교란·collider 반영)
- 1문장: 결론/향후 연구 방향
"""

REVIEW_INSTRUCTION = """\
당신은 학술지 동료심사위원(reviewer)입니다. 아래 입력 패킷을 기준 사실로 삼아, 주어진 **Discussion 초안**을
적대적으로 비판적 검토하십시오. 목표는 약점을 찾아 개선점을 도출하는 것입니다.

검토 렌즈(각 항목에 구체적 코멘트):
1. 결과 해석의 임상적 타당성 (과대·과소 해석 여부)
2. 인과 표현 과용 / 관찰연구 한계 누락
3. 인용 근거: 패킷 허용 목록 밖 인용이나 근거 없는 주장
4. effect size + 95% CI 보고 적절성 (p-value 단독 보고 등)
5. Limitations 4항목(선택편향·측정편향·교란·collider) 충실 반영 여부
6. 논리 흐름·중복·누락

출력 형식 (Markdown):
- ## Major issues  (번호 목록, 각 항목에 '문제 → 권고 수정')
- ## Minor issues
- ## 살릴 점(strengths)  — 최종본에 유지할 좋은 표현
"""


def _print_status(payload):
    """기계 판독용 상태를 stdout에 JSON 한 줄로."""
    print(json.dumps(payload, ensure_ascii=False))


def _codex_cmd(model):
    cmd = ["codex"] + CODEX_BASE[:]
    if model:
        cmd += ["-m", model]
    return cmd


def _run_codex(prompt, out_path, model, timeout):
    """codex exec 실행. 최종 메시지를 out_path(-o)로 기록. (returncode, err) 반환."""
    cmd = _codex_cmd(model) + ["-o", out_path, "-"]
    try:
        proc = subprocess.run(
            cmd, input=prompt, text=True, capture_output=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return 2, f"codex 타임아웃 ({timeout}s)"
    except FileNotFoundError:
        return 1, "codex 실행 파일 없음"
    if proc.returncode != 0:
        return proc.returncode, (proc.stderr or proc.stdout or "codex 비정상 종료").strip()[:500]
    return 0, ""


def cmd_probe(args):
    """Codex 사용 가능 여부. 바이너리 존재 + (옵션) 실제 exec 프로브."""
    if shutil.which("codex") is None:
        _print_status({"codex_available": False, "reason": "codex not in PATH"})
        return 1
    if args.no_exec:
        _print_status({"codex_available": True, "reason": "binary present (exec probe skipped)"})
        return 0
    # 실제 호출 프로브 — 인증·런타임까지 확인 (미인증이면 여기서 걸러짐)
    tmp = tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False)
    tmp.close()
    out_file = tmp.name
    rc, err = _run_codex("Reply with the single token: READY", out_file,
                         args.model, min(args.timeout, 90))
    text = ""
    try:
        with open(out_file) as f:
            text = f.read()
    except OSError:
        pass
    finally:
        try:
            os.unlink(out_file)
        except OSError:
            pass
    if rc == 0 and "READY" in text.upper():
        _print_status({"codex_available": True, "reason": "exec probe ok"})
        return 0
    _print_status({"codex_available": False,
                   "reason": f"exec probe failed (rc={rc}): {err or 'no READY token'}"})
    return 1


def _read(path):
    with open(path) as f:
        return f.read()


def cmd_codex_draft(args):
    packet = _read(args.packet)
    prompt = f"{GROUNDING_RULES}\n\n{DRAFT_INSTRUCTION}\n\n=== 입력 패킷 ===\n{packet}\n"
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    rc, err = _run_codex(prompt, args.out, args.model, args.timeout)
    if rc == 0:
        _print_status({"stage": "codex-draft", "ok": True, "out": args.out})
        return 0
    _print_status({"stage": "codex-draft", "ok": False, "rc": rc, "error": err})
    return rc if rc in (1, 2) else 2


def cmd_codex_review(args):
    packet = _read(args.packet)
    draft = _read(args.draft)
    prompt = (f"{GROUNDING_RULES}\n\n{REVIEW_INSTRUCTION}\n\n"
              f"=== 입력 패킷 (기준 사실) ===\n{packet}\n\n"
              f"=== 검토 대상 Discussion 초안 ===\n{draft}\n")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    rc, err = _run_codex(prompt, args.out, args.model, args.timeout)
    if rc == 0:
        _print_status({"stage": "codex-review", "ok": True, "out": args.out})
        return 0
    _print_status({"stage": "codex-review", "ok": False, "rc": rc, "error": err})
    return rc if rc in (1, 2) else 2


def main():
    ap = argparse.ArgumentParser(description="Discussion 이중 저자 협업 — Codex 측 헬퍼")
    ap.add_argument("-m", "--model", default=None, help="Codex 모델 (기본: codex 설정값)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="초 단위 타임아웃")
    sp = ap.add_subparsers(dest="cmd", required=True)

    pp = sp.add_parser("probe", help="Codex 사용 가능 여부 (exit 0=가능)")
    pp.add_argument("--no-exec", action="store_true",
                    help="실제 호출 없이 바이너리 존재만 확인 (빠름, 인증 미확인)")
    pp.set_defaults(func=cmd_probe)

    pd = sp.add_parser("codex-draft", help="Codex Discussion 초안")
    pd.add_argument("--packet", required=True)
    pd.add_argument("--out", required=True)
    pd.set_defaults(func=cmd_codex_draft)

    pr = sp.add_parser("codex-review", help="Codex 교차 검토")
    pr.add_argument("--draft", required=True)
    pr.add_argument("--packet", required=True)
    pr.add_argument("--out", required=True)
    pr.set_defaults(func=cmd_codex_review)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
