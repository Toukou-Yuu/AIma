"""ASGI 入口：``uvicorn web.api.main:app --reload``。

可编辑安装后无需手动 ``PYTHONPATH``。
"""

from web.api.app import app

__all__ = ["app"]
