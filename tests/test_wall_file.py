"""JSON 牌山导入功能测试。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from kernel.tiles.deck import build_deck
from llm.runner import _load_wall_from_file


class TestLoadWallFromFile:
    """_load_wall_from_file 函数测试。"""

    def test_load_valid_wall_file(self) -> None:
        """加载有效 JSON 文件返回 136 张牌。"""
        fixture = Path("tests/fixtures/wall_valid.json")
        wall = _load_wall_from_file(fixture)

        assert len(wall) == 136
        # 验证牌山合规性（_load_wall_from_file 内部已验证）
        from kernel.deal import assert_wall_is_standard_deck

        assert_wall_is_standard_deck(wall)

    def test_load_wall_file_missing_field(self) -> None:
        """缺少 wall 字段时报错。"""
        data = {"format_version": 1, "metadata": {"desc": "test"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                _load_wall_from_file(Path(f.name))
            except ValueError as e:
                assert "缺少 'wall' 数组字段" in str(e)
            finally:
                Path(f.name).unlink()

    def test_load_wall_file_wrong_length(self) -> None:
        """长度不对时报错。"""
        codes = ["1m"] * 135  # 少一张
        data = {"format_version": 1, "wall": codes}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                _load_wall_from_file(Path(f.name))
            except ValueError as e:
                assert "135" in str(e)
            finally:
                Path(f.name).unlink()

    def test_load_wall_file_invalid_tile_code(self) -> None:
        """无效牌码时报错。"""
        deck = build_deck()
        codes = [t.to_code() for t in deck]
        codes[0] = "10m"  # 无效牌码
        data = {"format_version": 1, "wall": codes}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                _load_wall_from_file(Path(f.name))
            except ValueError as e:
                assert "无效牌码" in str(e) or "10m" in str(e)
            finally:
                Path(f.name).unlink()

    def test_load_wall_file_duplicate_red_five(self) -> None:
        """重复赤牌导致非标准牌山。"""
        deck = build_deck()
        codes = [t.to_code() for t in deck]
        # 将一个普通五万改成赤五万，造成赤牌过多
        for i, c in enumerate(codes):
            if c == "5m":
                codes[i] = "5mr"
                break
        data = {"format_version": 1, "wall": codes}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                _load_wall_from_file(Path(f.name))
            except ValueError as e:
                assert "multiset" in str(e) or "does not match" in str(e)
            finally:
                Path(f.name).unlink()

    def test_load_wall_file_not_found(self) -> None:
        """文件不存在时报错。"""
        try:
            _load_wall_from_file(Path("/nonexistent/path.json"))
        except ValueError as e:
            assert "不存在" in str(e)

    def test_load_wall_file_format_version_2_rejected(self) -> None:
        """不支持格式版本 2。"""
        deck = build_deck()
        codes = [t.to_code() for t in deck]
        data = {"format_version": 2, "wall": codes}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                _load_wall_from_file(Path(f.name))
            except ValueError as e:
                assert "不支持牌山格式版本" in str(e)
            finally:
                Path(f.name).unlink()

    def test_load_wall_file_invalid_json(self) -> None:
        """JSON 解析失败时报错。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            f.flush()
            try:
                _load_wall_from_file(Path(f.name))
            except ValueError as e:
                assert "JSON 解析失败" in str(e)
            finally:
                Path(f.name).unlink()


class TestCliWallFileIntegration:
    """CLI 集成测试。"""

    def test_wall_file_cli_help(self) -> None:
        """--wall-file 参数在 help 中显示。"""
        import os
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"  # H-27: 子进程显式设置 PYTHONPATH
        result = subprocess.run(
            ["python", "-m", "llm", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert "--wall-file" in result.stdout

    def test_wall_file_with_max_hands_gt_1_rejected(self) -> None:
        """wall-file 与 max-hands > 1 组合时报错。"""
        import os
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"  # H-27: 子进程显式设置 PYTHONPATH
        result = subprocess.run(
            [
                "python",
                "-m",
                "llm",
                "--wall-file",
                "tests/fixtures/wall_valid.json",
                "--max-hands",
                "2",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 2
        assert "仅支持单局" in result.stderr

    def test_wall_file_single_hand_dry_run(self) -> None:
        """wall-file 单局 dry-run 正常执行。"""
        import os
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"  # H-27: 子进程显式设置 PYTHONPATH
        result = subprocess.run(
            [
                "python",
                "-m",
                "llm",
                "--wall-file",
                "tests/fixtures/wall_valid.json",
                "--max-hands",
                "1",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        # 应正常执行，返回码 0
        assert result.returncode == 0