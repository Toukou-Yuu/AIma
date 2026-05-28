"""UI artifact viewer.

data_source模块不依赖textual，可在无UI环境下使用。
ViewerApp需要textual，仅在需要时导入。
"""

from __future__ import annotations

from ui.viewer.data_source import ExperimentInfo, JobInfo, RunDataSource

__all__ = ["ExperimentInfo", "JobInfo", "RunDataSource"]

# ViewerApp需要textual，延迟导入避免阻塞非UI场景
def get_viewer_app() -> type:
    """获取ViewerApp类（需要textual环境）."""
    try:
        from ui.viewer.app import ViewerApp
        return ViewerApp
    except ImportError as e:
        raise ImportError(
            "ViewerApp需要textual库。请安装: pip install textual"
        ) from e
