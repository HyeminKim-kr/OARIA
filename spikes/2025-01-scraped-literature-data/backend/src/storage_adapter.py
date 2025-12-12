"""
OARIA Spike - 스토리지 어댑터

Local/GCS 자동 스위칭 스토리지 어댑터입니다.

MODE에 따라:
- local: 파일 시스템에 저장
- gcp: Google Cloud Storage에 저장

이 설계의 이유:
1. 동일한 인터페이스로 로컬/클라우드 저장소 사용
2. 테스트 시 GCS 비용 없이 로컬에서 검증
3. 프로덕션 배포 시 코드 변경 없이 GCS 사용
"""

import os
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

from .config import settings


class StorageAdapter(ABC):
    """스토리지 어댑터 추상 클래스"""
    
    @abstractmethod
    def save(self, pmcid: str, content: str) -> str:
        """Full-text XML 저장"""
        pass
    
    @abstractmethod
    def load(self, path: str) -> Optional[str]:
        """저장된 파일 읽기"""
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """파일 존재 여부 확인"""
        pass
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        """파일 삭제"""
        pass


class LocalStorageAdapter(StorageAdapter):
    """
    로컬 파일 시스템 스토리지
    
    개발/테스트 환경에서 사용합니다.
    Docker 볼륨으로 영속성을 보장합니다.
    """
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 LocalStorage initialized at: {self.base_path}")
    
    def _get_path(self, pmcid: str) -> Path:
        """PMCID 기반 파일 경로 생성"""
        return self.base_path / f"{pmcid}.xml"
    
    def save(self, pmcid: str, content: str) -> str:
        """Full-text XML 저장"""
        path = self._get_path(pmcid)
        path.write_text(content, encoding="utf-8")
        return str(path)
    
    def load(self, path: str) -> Optional[str]:
        """저장된 파일 읽기"""
        file_path = Path(path)
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None
    
    def exists(self, path: str) -> bool:
        """파일 존재 여부 확인"""
        return Path(path).exists()
    
    def delete(self, path: str) -> bool:
        """파일 삭제"""
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class GCSStorageAdapter(StorageAdapter):
    """
    Google Cloud Storage 어댑터
    
    프로덕션 환경에서 사용합니다.
    GCS 결제 정보가 없으면 LocalStorageAdapter로 폴백합니다.
    """
    
    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or settings.gcs_bucket
        self._client = None
        self._bucket = None
        
        if not self.bucket_name:
            print("⚠️  GCS_BUCKET not set, falling back to local storage")
            self._fallback = LocalStorageAdapter()
        else:
            try:
                from google.cloud import storage
                self._client = storage.Client()
                self._bucket = self._client.bucket(self.bucket_name)
                print(f"☁️  GCS Storage initialized: {self.bucket_name}")
                self._fallback = None
            except Exception as e:
                print(f"⚠️  GCS initialization failed: {e}, falling back to local")
                self._fallback = LocalStorageAdapter()
    
    def _get_blob_name(self, pmcid: str) -> str:
        """PMCID 기반 blob 이름 생성"""
        return f"fulltext/{pmcid}.xml"
    
    def save(self, pmcid: str, content: str) -> str:
        """Full-text XML 저장"""
        if self._fallback:
            return self._fallback.save(pmcid, content)
        
        blob_name = self._get_blob_name(pmcid)
        blob = self._bucket.blob(blob_name)
        blob.upload_from_string(content, content_type="application/xml")
        return f"gs://{self.bucket_name}/{blob_name}"
    
    def load(self, path: str) -> Optional[str]:
        """저장된 파일 읽기"""
        if self._fallback:
            return self._fallback.load(path)
        
        try:
            if path.startswith("gs://"):
                # gs://bucket/path 형식 파싱
                parts = path[5:].split("/", 1)
                blob_name = parts[1] if len(parts) > 1 else parts[0]
            else:
                blob_name = path
            
            blob = self._bucket.blob(blob_name)
            return blob.download_as_text()
        except Exception:
            return None
    
    def exists(self, path: str) -> bool:
        """파일 존재 여부 확인"""
        if self._fallback:
            return self._fallback.exists(path)
        
        try:
            if path.startswith("gs://"):
                parts = path[5:].split("/", 1)
                blob_name = parts[1] if len(parts) > 1 else parts[0]
            else:
                blob_name = path
            
            blob = self._bucket.blob(blob_name)
            return blob.exists()
        except Exception:
            return False
    
    def delete(self, path: str) -> bool:
        """파일 삭제"""
        if self._fallback:
            return self._fallback.delete(path)
        
        try:
            if path.startswith("gs://"):
                parts = path[5:].split("/", 1)
                blob_name = parts[1] if len(parts) > 1 else parts[0]
            else:
                blob_name = path
            
            blob = self._bucket.blob(blob_name)
            blob.delete()
            return True
        except Exception:
            return False


def get_storage() -> StorageAdapter:
    """
    설정에 따라 적절한 스토리지 어댑터 반환
    
    GCP 환경이 없을 때는 자동으로 로컬 스토리지로 폴백합니다.
    """
    if settings.storage_is_local:
        return LocalStorageAdapter()
    else:
        return GCSStorageAdapter()


# 싱글톤 인스턴스
_storage_instance: Optional[StorageAdapter] = None


def get_storage_instance() -> StorageAdapter:
    """싱글톤 스토리지 인스턴스 반환"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_storage()
    return _storage_instance
