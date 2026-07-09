"""CredentialStore: 掩码 status、keychain/file 双后端。

明文绝不写入日志/status 输出；status 仅返回掩码串。本模块不包含任何真实密钥。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

SERVICE_NAME = "probe"
_NOT_SET = "<not set>"


class CredentialBackendUnavailable(RuntimeError):
    """凭据后端不可用（如 keychain 缺失/锁定）。由调用方退回 file/env。"""


def mask(value: str) -> str:
    """形如 ``sk-…1234``：首三字符 + ``…`` + 末四字符。

    短于 7 字符的值整体掩码为 ``…``（重复至原长度的 ``…`` 串），绝不泄露明文。
    """
    if value is None:
        return _NOT_SET
    if len(value) < 7:
        return "…" * max(1, len(value))
    return f"{value[:3]}…{value[-4:]}"


class CredentialStore:
    """凭据存储。支持 ``keychain`` 与 ``file`` 两种后端。

    ``status`` 永远返回掩码串；``get`` 返回明文供内部使用。
    """

    def __init__(self, backend: str = "file", store_dir: Optional[os.PathLike | str] = None):
        self.backend = backend
        if backend == "file":
            if store_dir is None:
                raise ValueError("file backend 需要 store_dir 参数")
            self._store_dir = Path(store_dir)
            self._store_dir.mkdir(parents=True, exist_ok=True)
            self._path = self._store_dir / ".credentials.json"
        elif backend == "keychain":
            try:
                import keyring  # noqa: F401
            except ImportError as exc:  # pragma: no cover
                raise CredentialBackendUnavailable(
                    "keyring 库未安装，无法使用 keychain 后端"
                ) from exc
            self._store_dir = None
            self._path = None
        else:
            raise ValueError(f"未知 backend: {backend!r}（可选 'file' / 'keychain'）")

    # ---- file 后端读写 --------------------------------------------------
    def _load(self) -> dict:
        if self.backend != "file":
            raise RuntimeError("仅 file 后端支持 _load")
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return {}
            return data
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        if self.backend != "file":
            raise RuntimeError("仅 file 后端支持 _save")
        # 写入临时文件后原子替换，并收紧权限为 600。
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=0)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self._path)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    # ---- 公共 API -------------------------------------------------------
    def get(self, key: str) -> Optional[str]:
        if self.backend == "keychain":
            try:
                import keyring
            except ImportError as exc:  # pragma: no cover
                raise CredentialBackendUnavailable(
                    "keyring 库不可用"
                ) from exc
            try:
                return keyring.get_password(SERVICE_NAME, key)
            except Exception as exc:
                raise CredentialBackendUnavailable(
                    f"keychain 读取失败: {exc}"
                ) from exc
        data = self._load()
        val = data.get(key)
        return val if isinstance(val, str) else None

    def set(self, key: str, value: str) -> None:
        self.update(key, value)

    def update(self, key: str, value: str) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("key 必须为非空字符串")
        if not isinstance(value, str):
            raise ValueError("value 必须为字符串")
        if self.backend == "keychain":
            try:
                import keyring
            except ImportError as exc:  # pragma: no cover
                raise CredentialBackendUnavailable(
                    "keyring 库不可用"
                ) from exc
            try:
                keyring.set_password(SERVICE_NAME, key, value)
            except Exception as exc:
                raise CredentialBackendUnavailable(
                    f"keychain 写入失败: {exc}"
                ) from exc
            return
        data = self._load()
        data[key] = value
        self._save(data)

    def clear(self, key: str) -> None:
        if self.backend == "keychain":
            try:
                import keyring
            except ImportError as exc:  # pragma: no cover
                raise CredentialBackendUnavailable(
                    "keyring 库不可用"
                ) from exc
            try:
                keyring.delete_password(SERVICE_NAME, key)
            except Exception as exc:
                # 不存在视为幂等成功；其余错误视为后端不可用。
                msg = str(exc).lower()
                if "nope" in msg or "not found" in msg or "not exist" in msg:
                    return
                raise CredentialBackendUnavailable(
                    f"keychain 删除失败: {exc}"
                ) from exc
            return
        data = self._load()
        if key in data:
            del data[key]
            self._save(data)

    def status(self, key: str) -> str:
        """返回掩码串；key 未设置返回 ``<not set>``。永不回显明文。"""
        val = self.get(key)
        if val is None:
            return _NOT_SET
        return mask(val)
