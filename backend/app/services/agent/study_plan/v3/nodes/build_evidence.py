"""Node 6: build_evidence_pack - Evidence Pack 구축"""

import json
import logging
import uuid

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import BUILD_EVIDENCE_SYSTEM, BUILD_EVIDENCE_USER
from ..state import (
    ClaimType,
    EvidencePack,
    EvidenceSnippet,
    EvidenceSummaryByClaim,
    StudyPlanState,
)

logger = logging.getLogger(__name__)


async def build_evidence_pack(state: StudyPlanState) -> dict:
    """
    검색 결과에서 Evidence Pack을 구축합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - evidence_snippets: list[EvidenceSnippet]
        - evidence_packs: list[EvidencePack]
        - evidence_summary: EvidenceSummaryByClaim
    """
    prior_studies = state.get("prior_studies", [])
    hypothesis = state.get("hypothesis")
    test_questions = state.get("test_questions", [])

    logger.info(f"Building evidence pack from {len(prior_studies)} studies")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "independent_variable": hypothesis.independent_variable,
                "dependent_variable": hypothesis.dependent_variable,
            }

        tq_list = [
            {"category": q.category.value, "question": q.question}
            for q in test_questions
        ]

        # 검색 결과를 간략화하여 전달 (RAG 스니펫 포함)
        studies_summary = []
        for s in prior_studies[:20]:  # 상위 20개만
            study_data = {
                "paper_id": s.get("paper_id", ""),
                "title": s.get("title", ""),
                "abstract": s.get("abstract", "")[:500],
                "section": s.get("section", ""),
            }
            # RAG에서 가져온 추가 스니펫이 있으면 포함
            if s.get("all_snippets"):
                study_data["snippets"] = [
                    {
                        "section": snip.get("section", ""),
                        "text": snip.get("text", "")[:300],
                        "relevance_score": snip.get("relevance_score", 0.5),
                    }
                    for snip in s["all_snippets"][:3]  # 논문당 최대 3개 스니펫
                ]
            studies_summary.append(study_data)

        user_prompt = BUILD_EVIDENCE_USER.format(
            search_results=json.dumps(studies_summary, ensure_ascii=False, indent=2),
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False),
            test_questions=json.dumps(tq_list, ensure_ascii=False),
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": BUILD_EVIDENCE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # Evidence Snippets 생성
        all_snippets = []
        all_packs = []

        # LLM 분석 결과
        llm_snippets = result.get("snippets", [])
        summary_data = result.get("summary", {})

        for study in prior_studies[:15]:
            paper_id = study.get("paper_id", f"paper_{uuid.uuid4().hex[:8]}")

            pack = EvidencePack(
                paper_id=paper_id,
                title=study.get("title", ""),
                journal=study.get("journal", ""),
                year=study.get("year", 0),
            )

            # RAG에서 가져온 실제 스니펫 사용
            rag_snippets = study.get("all_snippets", [])
            if rag_snippets:
                for i, rs in enumerate(rag_snippets[:5]):
                    # LLM 분석에서 claim_type 매칭 시도
                    claim_type = ClaimType.RESULT
                    for ls in llm_snippets:
                        if ls.get("paper_id") == paper_id or rs.get("text", "")[:50] in ls.get("text", ""):
                            try:
                                claim_type = ClaimType(ls.get("claim_type", "result"))
                            except ValueError:
                                pass
                            break

                    snippet = EvidenceSnippet(
                        snippet_id=rs.get("snippet_id", f"{paper_id}_snippet_{i}"),
                        paper_id=paper_id,
                        section=rs.get("section", "abstract"),
                        offset_start=rs.get("offset_start", 0),
                        offset_end=rs.get("offset_end", len(rs.get("text", ""))),
                        claim_type=claim_type,
                        text=rs.get("text", "")[:500],
                        relevance_score=rs.get("relevance_score", 0.5),
                    )
                    all_snippets.append(snippet)
                    pack.snippets.append(snippet)
            else:
                # RAG 스니펫이 없으면 abstract 기반으로 생성
                abstract = study.get("abstract", "")
                if abstract:
                    snippet = EvidenceSnippet(
                        snippet_id=f"{paper_id}_abstract_0",
                        paper_id=paper_id,
                        section=study.get("section", "abstract"),
                        offset_start=study.get("offset_start", 0),
                        offset_end=study.get("offset_end", len(abstract)),
                        claim_type=ClaimType.RESULT,
                        text=abstract[:500],
                        relevance_score=study.get("relevance_score", 0.5),
                    )
                    all_snippets.append(snippet)
                    pack.snippets.append(snippet)

            # Pack 요약 필드 채우기
            if summary_data.get("models"):
                pack.model_used = ", ".join(summary_data["models"][:3])
            if summary_data.get("perturbations"):
                pack.perturbation_used = ", ".join(summary_data["perturbations"][:3])
            if summary_data.get("readouts"):
                pack.readout_used = ", ".join(summary_data["readouts"][:3])
            if summary_data.get("key_findings"):
                pack.key_finding = summary_data["key_findings"][0] if summary_data["key_findings"] else ""
            if summary_data.get("limitations"):
                pack.limitations = summary_data["limitations"][:3]

            all_packs.append(pack)

        # Evidence Summary 생성
        summary_data = result.get("summary", {})
        evidence_summary = EvidenceSummaryByClaim(
            models=[{"model": m} for m in summary_data.get("models", [])],
            perturbations=[{"perturbation": p} for p in summary_data.get("perturbations", [])],
            readouts=[{"readout": r} for r in summary_data.get("readouts", [])],
            results=[{"finding": f} for f in summary_data.get("key_findings", [])],
            limitations=[{"limitation": l} for l in summary_data.get("limitations", [])],
        )

        logger.info(
            f"Built {len(all_packs)} evidence packs, "
            f"{len(all_snippets)} snippets"
        )

        return {
            "evidence_snippets": all_snippets,
            "evidence_packs": all_packs,
            "evidence_summary": evidence_summary,
            "status_detail": "evidence_packed",
        }

    except Exception as e:
        logger.error(f"Error building evidence pack: {e}")
        return {
            "evidence_snippets": [],
            "evidence_packs": [],
            "evidence_summary": None,
            "error": str(e),
            "status_detail": "evidence_error",
        }
