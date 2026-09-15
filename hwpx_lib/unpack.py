"""
HWPX 패키지 ZIP 입출력.
참조: references/01-hwpx-package.md
"""
import os
import shutil
import tempfile
import zipfile
from typing import Optional, List


def open_hwpx(path: str) -> str:
    """
    HWPX 파일을 임시 디렉터리에 풀고 루트 경로를 반환.
    mimetype 엔트리 확인만 하고, 없으면 경고(진행).
    반환한 tmp_dir은 호출자가 close_hwpx로 정리.
    """
    tmp = tempfile.mkdtemp(prefix="hwpx_")
    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()
        if names and names[0] == "mimetype":
            info = z.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                pass  # 경고만 (추후 strict 옵션)
            z.extract("mimetype", tmp)
        z.extractall(tmp)
    return tmp


def close_hwpx(tmp_dir: str) -> None:
    shutil.rmtree(tmp_dir, ignore_errors=True)


def find_in_tmp(tmp_dir: str, relpath: str) -> Optional[str]:
    """대소문자/위치 유연하게 파일 찾기. 있으면 절대 경로, 없으면 None."""
    target = os.path.normpath(os.path.join(tmp_dir, relpath))
    if os.path.isfile(target):
        return target
    basename = os.path.basename(relpath)
    for root, dirs, files in os.walk(tmp_dir):
        for f in files:
            if f.lower() == basename.lower():
                return os.path.join(root, f)
    return None


def list_texts(tmp_dir: str) -> List[str]:
    """임시 디렉터리 내 모든 파일 상대 경로 목록."""
    out = []
    for root, dirs, files in os.walk(tmp_dir):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, tmp_dir).replace(os.sep, "/")
            out.append(rel)
    return out
