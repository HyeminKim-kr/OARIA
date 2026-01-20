import { Info } from 'lucide-react';

export function LabHelpPanel() {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-5">
      <h3 className="flex items-center gap-2 font-semibold text-blue-900">
        <Info className="h-5 w-5" />
        RAG (Retrieval-Augmented Generation) 이란?
      </h3>
      <p className="mt-2 text-sm text-blue-800">
        RAG는 질문에 답변하기 전에 관련 문서를 먼저 검색하여, 그 내용을 바탕으로 AI가 답변을
        생성하는 기술입니다. 이를 통해 AI가 최신 정보나 특정 도메인 지식을 활용할 수 있습니다.
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-lg bg-white p-4">
          <h4 className="font-medium text-gray-900">검색 테스트</h4>
          <p className="mt-1 text-sm text-gray-600">
            질문과 관련된 논문 조각(청크)을 찾아 보여줍니다. 검색 품질을 확인할 수 있습니다.
          </p>
          <ul className="mt-2 space-y-1 text-xs text-gray-500">
            <li>
              <strong>Score</strong>: 유사도 점수 (높을수록 관련성 높음)
            </li>
            <li>
              <strong>Chunk</strong>: 논문에서 잘린 텍스트 조각
            </li>
            <li>
              <strong>Latency</strong>: 검색 소요 시간
            </li>
          </ul>
        </div>
        <div className="rounded-lg bg-white p-4">
          <h4 className="font-medium text-gray-900">답변 생성 테스트</h4>
          <p className="mt-1 text-sm text-gray-600">
            검색된 문서를 바탕으로 AI가 답변을 생성합니다. 답변의 품질과 출처를 확인할 수
            있습니다.
          </p>
          <ul className="mt-2 space-y-1 text-xs text-gray-500">
            <li>
              <strong>References</strong>: 답변에 사용된 출처 문서
            </li>
            <li>
              <strong>Token</strong>: LLM API 사용량 (비용과 직결)
            </li>
            <li>
              <strong>LLM Latency</strong>: AI 답변 생성 시간
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-4 rounded-lg bg-white p-4">
        <h4 className="font-medium text-gray-900">파라미터 설명</h4>
        <div className="mt-2 grid gap-2 text-sm md:grid-cols-3">
          <div>
            <strong className="text-gray-700">Limit (결과 개수)</strong>
            <p className="text-xs text-gray-500">검색할 문서 조각 개수. 많으면 정확도↑, 속도↓</p>
          </div>
          <div>
            <strong className="text-gray-700">Alpha (하이브리드 가중치)</strong>
            <p className="text-xs text-gray-500">
              0 = 키워드 검색만, 1 = 벡터(의미) 검색만
              <br />
              0.7 권장: 의미 70% + 키워드 30% 조합
            </p>
          </div>
          <div>
            <strong className="text-gray-700">Reranker</strong>
            <p className="text-xs text-gray-500">
              BGE Cross-Encoder로 검색 결과 재평가
              <br />
              관련 없는 결과 필터링, 정확도↑, 속도↓
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
