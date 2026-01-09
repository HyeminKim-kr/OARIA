"""RAG 컴포넌트 레지스트리

Strategy Pattern + Registry Pattern으로 RAG 컴포넌트들을 관리합니다.
각 컴포넌트는 @register_* 데코레이터로 자동 등록됩니다.
"""

from typing import TypeVar, Callable, Any
from functools import wraps

# 타입 변수
T = TypeVar("T")

# 레지스트리 저장소
_registries: dict[str, dict[str, type]] = {
    "chunker": {},
    "embedder": {},
    "retriever": {},
    "reranker": {},
    "classifier": {},
    "evaluator": {},
}

# 인스턴스 캐시 (싱글톤 패턴)
_instances: dict[str, dict[str, Any]] = {
    "chunker": {},
    "embedder": {},
    "retriever": {},
    "reranker": {},
    "classifier": {},
    "evaluator": {},
}


def _create_register_decorator(component_type: str) -> Callable[[type[T]], type[T]]:
    """레지스트리 등록 데코레이터 생성 팩토리"""

    def decorator(cls: type[T]) -> type[T]:
        """컴포넌트를 레지스트리에 등록"""
        if not hasattr(cls, "name"):
            raise ValueError(f"{cls.__name__}에 'name' 속성이 필요합니다.")

        name = cls.name
        if name in _registries[component_type]:
            raise ValueError(
                f"{component_type} '{name}'이(가) 이미 등록되어 있습니다: "
                f"{_registries[component_type][name].__name__}"
            )

        _registries[component_type][name] = cls
        return cls

    return decorator


def _get_component(
    component_type: str,
    name: str,
    singleton: bool = True,
    **kwargs,
) -> Any:
    """레지스트리에서 컴포넌트 인스턴스 가져오기

    Args:
        component_type: 컴포넌트 타입 (chunker, embedder, etc.)
        name: 등록된 이름
        singleton: True면 캐시된 인스턴스 반환, False면 새 인스턴스
        **kwargs: 인스턴스 생성 시 전달할 인자

    Returns:
        컴포넌트 인스턴스
    """
    if name not in _registries[component_type]:
        available = list(_registries[component_type].keys())
        raise ValueError(
            f"'{name}' {component_type}을(를) 찾을 수 없습니다. "
            f"사용 가능: {available}"
        )

    # 싱글톤 캐시 확인
    if singleton and name in _instances[component_type]:
        return _instances[component_type][name]

    # 새 인스턴스 생성
    cls = _registries[component_type][name]
    instance = cls(**kwargs)

    # 싱글톤 캐시 저장
    if singleton:
        _instances[component_type][name] = instance

    return instance


def _list_components(component_type: str) -> list[str]:
    """등록된 컴포넌트 이름 목록 반환"""
    return list(_registries[component_type].keys())


def _get_component_info(component_type: str) -> list[dict[str, Any]]:
    """등록된 컴포넌트들의 상세 정보 반환"""
    info_list = []
    for name, cls in _registries[component_type].items():
        info = {
            "name": name,
            "class_name": cls.__name__,
            "module": cls.__module__,
            "description": cls.__doc__ or "",
        }
        # 인스턴스가 있으면 config도 포함
        if name in _instances[component_type]:
            instance = _instances[component_type][name]
            if hasattr(instance, "get_config"):
                info["config"] = instance.get_config()
        info_list.append(info)
    return info_list


# ============================================================
# 데코레이터 정의
# ============================================================

register_chunker = _create_register_decorator("chunker")
register_embedder = _create_register_decorator("embedder")
register_retriever = _create_register_decorator("retriever")
register_reranker = _create_register_decorator("reranker")
register_classifier = _create_register_decorator("classifier")
register_evaluator = _create_register_decorator("evaluator")


# ============================================================
# 조회 함수 정의
# ============================================================

# Chunker
def get_chunker(name: str, singleton: bool = True, **kwargs):
    """청킹 전략 인스턴스 가져오기"""
    return _get_component("chunker", name, singleton, **kwargs)


def list_chunkers() -> list[str]:
    """등록된 청킹 전략 목록"""
    return _list_components("chunker")


def get_chunker_info() -> list[dict[str, Any]]:
    """청킹 전략 상세 정보"""
    return _get_component_info("chunker")


# Embedder
def get_embedder(name: str, singleton: bool = True, **kwargs):
    """임베딩 모델 인스턴스 가져오기"""
    return _get_component("embedder", name, singleton, **kwargs)


def list_embedders() -> list[str]:
    """등록된 임베딩 모델 목록"""
    return _list_components("embedder")


def get_embedder_info() -> list[dict[str, Any]]:
    """임베딩 모델 상세 정보"""
    return _get_component_info("embedder")


# Retriever
def get_retriever(name: str, singleton: bool = True, **kwargs):
    """검색 전략 인스턴스 가져오기"""
    return _get_component("retriever", name, singleton, **kwargs)


def list_retrievers() -> list[str]:
    """등록된 검색 전략 목록"""
    return _list_components("retriever")


def get_retriever_info() -> list[dict[str, Any]]:
    """검색 전략 상세 정보"""
    return _get_component_info("retriever")


# Reranker
def get_reranker(name: str, singleton: bool = True, **kwargs):
    """리랭킹 모델 인스턴스 가져오기"""
    return _get_component("reranker", name, singleton, **kwargs)


def list_rerankers() -> list[str]:
    """등록된 리랭킹 모델 목록"""
    return _list_components("reranker")


def get_reranker_info() -> list[dict[str, Any]]:
    """리랭킹 모델 상세 정보"""
    return _get_component_info("reranker")


# Classifier
def get_classifier(name: str, singleton: bool = True, **kwargs):
    """도메인 분류기 인스턴스 가져오기"""
    return _get_component("classifier", name, singleton, **kwargs)


def list_classifiers() -> list[str]:
    """등록된 도메인 분류기 목록"""
    return _list_components("classifier")


def get_classifier_info() -> list[dict[str, Any]]:
    """도메인 분류기 상세 정보"""
    return _get_component_info("classifier")


# Evaluator
def get_evaluator(name: str, singleton: bool = True, **kwargs):
    """품질 평가기 인스턴스 가져오기"""
    return _get_component("evaluator", name, singleton, **kwargs)


def list_evaluators() -> list[str]:
    """등록된 품질 평가기 목록"""
    return _list_components("evaluator")


def get_evaluator_info() -> list[dict[str, Any]]:
    """품질 평가기 상세 정보"""
    return _get_component_info("evaluator")


# ============================================================
# 전체 조회
# ============================================================

def get_all_strategies() -> dict[str, list[str]]:
    """모든 컴포넌트 타입별 등록된 전략 목록"""
    return {
        "chunkers": list_chunkers(),
        "embedders": list_embedders(),
        "retrievers": list_retrievers(),
        "rerankers": list_rerankers(),
        "classifiers": list_classifiers(),
        "evaluators": list_evaluators(),
    }


def get_all_strategies_info() -> dict[str, list[dict[str, Any]]]:
    """모든 컴포넌트 타입별 상세 정보"""
    return {
        "chunkers": get_chunker_info(),
        "embedders": get_embedder_info(),
        "retrievers": get_retriever_info(),
        "rerankers": get_reranker_info(),
        "classifiers": get_classifier_info(),
        "evaluators": get_evaluator_info(),
    }
