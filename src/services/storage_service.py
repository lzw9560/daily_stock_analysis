# -*- coding: utf-8 -*-
"""
第三方存储服务 — 报告文件上传与公开 URL 生成.

当前支持:
- tempsh: https://temp.sh（首选，3 天后过期）
- 0x0st: https://0x0.st（降级，当前已关闭上传）
- catbox: https://catbox.moe（最终降级）
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_UPLOADERS: list[tuple[str, callable]] = []


def _init_uploaders():
    if _UPLOADERS:
        return
    _UPLOADERS.append(("temp.sh", _upload_to_tempsh))
    _UPLOADERS.append(("0x0.st", _upload_to_0x0st))
    _UPLOADERS.append(("catbox.moe", _upload_to_catbox))


def upload_report(filepath: str | Path) -> str:
    """上传报告文件到第三方存储，返回公开可访问 URL.

    按固定提供商顺序尝试，失败时自动切换。

    Args:
        filepath: 本地文件路径

    Returns:
        公开可访问的 URL，全部失败时返回空字符串
    """
    provider = os.getenv("STORAGE_PROVIDER", "").lower().strip()
    if not provider:
        logger.debug("STORAGE_PROVIDER 未配置，跳过上传")
        return ""

    _init_uploaders()

    if provider in ("tempsh", "0x0st", "catbox"):
        for name, fn in _UPLOADERS:
            try:
                url = fn(filepath)
                if url:
                    logger.info("报告已上传至 %s: %s", name, url)
                    return url
            except Exception as exc:
                logger.warning("%s 上传失败: %s", name, exc)
        logger.error("所有存储提供商失败，报告无法获取公开链接")
        return ""

    logger.warning("不支持的 STORAGE_PROVIDER: %s", provider)
    return ""


def _upload_to_tempsh(filepath: str | Path) -> str:
    """通过 temp.sh 上传文件（免费，无需注册，3 天后过期）."""
    with open(filepath, "rb") as f:
        resp = requests.post(
            "https://temp.sh/upload",
            files={"file": f},
            timeout=120,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url:
        raise RuntimeError("temp.sh 返回空 URL")
    return url


def _upload_to_0x0st(filepath: str | Path) -> str:
    """通过 0x0.st 上传文件."""
    url = os.getenv("0X0ST_UPLOAD_URL", "https://0x0.st")
    with open(filepath, "rb") as f:
        resp = requests.post(url, files={"file": f}, timeout=60)
    resp.raise_for_status()
    upload_url = resp.text.strip()
    if not upload_url:
        raise RuntimeError("0x0.st 返回空 URL")
    return upload_url


def _upload_to_catbox(filepath: str | Path) -> str:
    """通过 catbox.moe 上传文件（免费，无需注册，文件不自动过期）."""
    with open(filepath, "rb") as f:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": f},
            timeout=120,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url:
        raise RuntimeError("catbox.moe 返回空 URL")
    return url
