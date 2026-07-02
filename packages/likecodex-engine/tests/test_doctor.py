"""Tests for the Doctor diagnostics module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from likecodex_engine.doctor import DiagnosisResult, Doctor


class TestDiagnosisResult:
    """Unit tests for DiagnosisResult data model."""

    def test_default_values(self) -> None:
        result = DiagnosisResult()
        assert result.python_version == ""
        assert result.python_ok is False
        assert result.git_available is False
        assert result.errors == []
        assert result.warnings == []

    def test_to_dict_structure(self) -> None:
        result = DiagnosisResult(
            timestamp="2025-01-01T00:00:00",
            python_version="3.12.0",
            python_ok=True,
            git_available=True,
            git_version="git version 2.40.0",
            docker_available=False,
            node_available=True,
            node_version="v20.0.0",
            rust_available=False,
            cargo_available=False,
            deepseek_api_reachable=True,
        )
        d = result.to_dict()
        assert d["python"]["version"] == "3.12.0"
        assert d["python"]["ok"] is True
        assert d["git"]["available"] is True
        assert d["git"]["version"] == "git version 2.40.0"
        assert d["docker"]["available"] is False
        assert d["deepseek_api"]["reachable"] is True


class TestDoctor:
    """Unit tests for the Doctor diagnostics runner."""

    def test_check_python_ok(self) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        version = doctor._check_python(result)
        assert result.python_ok is True
        assert result.python_version == version
        # Python version should be current interpreter's version
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert version == expected

    def test_check_python_too_old(self) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        with patch.object(sys, "version_info", (3, 9, 0)):
            doctor._check_python(result)
        assert result.python_ok is False
        assert any("too old" in e for e in result.errors)

    @patch("shutil.which", return_value=None)
    def test_check_git_not_found(self, mock_which: MagicMock) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_git(result)
        assert result.git_available is False
        assert any("Git not found" in w for w in result.warnings)

    @patch("shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    def test_check_git_ok(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        mock_run.return_value.stdout = "git version 2.40.0\n"
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_git(result)
        assert result.git_available is True
        assert "2.40.0" in result.git_version

    @patch("shutil.which", return_value=None)
    def test_check_docker_not_found(self, mock_which: MagicMock) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_docker(result)
        assert result.docker_available is False
        assert any("Docker not found" in w for w in result.warnings)

    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_check_docker_ok(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_docker(result)
        assert result.docker_available is True

    @patch("shutil.which", return_value=None)
    def test_check_node_not_found(self, mock_which: MagicMock) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_node(result)
        assert result.node_available is False
        assert any("Node.js not found" in w for w in result.warnings)

    @patch("shutil.which", return_value="/usr/bin/node")
    @patch("subprocess.run")
    def test_check_node_ok(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        mock_run.return_value.stdout = "v22.0.0\n"
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_node(result)
        assert result.node_available is True
        assert "v22.0.0" in result.node_version

    @patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}" if x in ("rustc", "cargo") else None)
    def test_check_rust_ok(self, mock_which: MagicMock) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_rust(result)
        assert result.rust_available is True
        assert result.cargo_available is True

    @patch("shutil.which", return_value=None)
    def test_check_rust_not_found(self, mock_which: MagicMock) -> None:
        doctor = Doctor()
        result = DiagnosisResult()
        doctor._check_rust(result)
        assert result.rust_available is False
        assert any("Rust toolchain not found" in w for w in result.warnings)

    @patch("httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_check_deepseek_api_reachable(self, mock_client: MagicMock) -> None:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_instance = mock_client.return_value
        mock_instance.__aenter__.return_value.get.return_value = mock_resp

        doctor = Doctor()
        result = DiagnosisResult()
        await doctor._check_deepseek_api(result)
        assert result.deepseek_api_reachable is True

    @patch("httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_check_deepseek_api_unreachable(self, mock_client: MagicMock) -> None:
        import httpx

        mock_instance = mock_client.return_value
        mock_instance.__aenter__.return_value.get.side_effect = httpx.HTTPError("Connection failed")

        doctor = Doctor()
        result = DiagnosisResult()
        await doctor._check_deepseek_api(result)
        assert result.deepseek_api_reachable is False
        assert any("unreachable" in w.lower() for w in result.warnings)

    @patch.object(Doctor, "_check_python", return_value="3.12.0")
    @patch.object(Doctor, "_check_git")
    @patch.object(Doctor, "_check_docker")
    @patch.object(Doctor, "_check_node")
    @patch.object(Doctor, "_check_rust")
    @patch.object(Doctor, "_check_deepseek_api", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_diagnose_full(
        self,
        mock_api: AsyncMock,
        mock_rust: MagicMock,
        mock_node: MagicMock,
        mock_docker: MagicMock,
        mock_git: MagicMock,
        mock_python: MagicMock,
    ) -> None:
        doctor = Doctor()
        result = await doctor.diagnose()
        assert isinstance(result, DiagnosisResult)
        assert result.timestamp != ""

    def test_print_report_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        doctor = Doctor()
        result = DiagnosisResult(python_ok=True, python_version="3.12.0")
        doctor.print_report(result, json_output=True)
        captured = capsys.readouterr()
        assert '"python"' in captured.out
