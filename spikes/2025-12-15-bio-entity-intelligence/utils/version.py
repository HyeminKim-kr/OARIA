"""
🔒 Version Guard for Dataset Compatibility
==========================================
Ensures datasets==2.18.0 is installed for BC5CDR compatibility
"""
import sys
import datasets
from utils.logger import error, success, box

REQUIRED_DATASETS_VERSION = "2.18.0"


def check_datasets_version() -> bool:
    """
    Check if the installed datasets version matches the required version.
    BC5CDR dataset requires datasets==2.18.0 due to script-based loading.
    
    Returns:
        bool: True if version matches, exits if not
    """
    current_version = datasets.__version__
    
    if current_version != REQUIRED_DATASETS_VERSION:
        error(f"datasets 버전 불일치!")
        box("VERSION MISMATCH", [
            f"현재 버전: datasets=={current_version}",
            f"필요 버전: datasets=={REQUIRED_DATASETS_VERSION}",
            "",
            "아래 명령어로 수정하세요:",
            "  pip uninstall datasets -y",
            f"  pip install datasets=={REQUIRED_DATASETS_VERSION}",
        ])
        sys.exit(1)
    
    success(f"datasets=={current_version} ✓")
    return True


def check_all_versions():
    """Run all version checks."""
    check_datasets_version()
