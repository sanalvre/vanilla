"""
Unit tests for GPU detection — mocks torch imports
since test machines may not have CUDA/MPS.
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

import services.gpu_detect as gpu_module
from services.gpu_detect import detect_gpu, GPUCapabilities


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the cached GPU result before each test."""
    gpu_module._cached = None
    yield
    gpu_module._cached = None


class TestDetectGPU:
    def test_no_torch_installed(self):
        """When torch is not installed, should return no GPU."""
        with patch.dict("sys.modules", {"torch": None}):
            # Force ImportError
            gpu_module._cached = None
            with patch("builtins.__import__", side_effect=_import_no_torch):
                result = detect_gpu()
                assert result.gpu is False
                assert result.gpu_type == "none"

    def test_cuda_available(self):
        """When CUDA is available, should detect it."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = detect_gpu()
            assert result.gpu is True
            assert result.gpu_type == "cuda"

    def test_mps_available(self):
        """When MPS (Apple Silicon) is available, should detect it."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = detect_gpu()
            assert result.gpu is True
            assert result.gpu_type == "mps"

    def test_no_gpu_with_torch(self):
        """When torch is installed but no GPU available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = detect_gpu()
            assert result.gpu is False
            assert result.gpu_type == "none"

    def test_caching(self):
        """Second call should return cached result."""
        gpu_module._cached = GPUCapabilities(gpu=True, gpu_type="cuda")
        result = detect_gpu()
        assert result.gpu is True
        assert result.gpu_type == "cuda"

    def test_gpu_capabilities_dataclass(self):
        cap = GPUCapabilities(gpu=True, gpu_type="mps")
        assert cap.gpu is True
        assert cap.gpu_type == "mps"


def _import_no_torch(name, *args, **kwargs):
    """Custom import that raises ImportError for torch."""
    if name == "torch":
        raise ImportError("No module named 'torch'")
    return original_import(name, *args, **kwargs)


original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
