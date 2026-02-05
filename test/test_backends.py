"""
Tests for maple.backend modules.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestPolicyBackendBase:
    """Tests for DockerPolicyBackend base class."""
    
    @pytest.mark.unit
    def test_encode_image_numpy(self, sample_image_b64):
        """Test encoding numpy image to base64."""
        from maple.backend.policy.base import PolicyBackend
        import numpy as np
        import base64
        from PIL import Image
        import io
        
        # Create a concrete subclass for testing
        class TestBackend(PolicyBackend):
            name = "test"
            IMAGE = "test:latest"
            HF_REPOS = {"v1": "org/model"}
        
        backend = TestBackend()
        
        # Create numpy image
        img_array = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        
        encoded = backend._encode_image(img_array)
        
        assert isinstance(encoded, str)
        # Should be valid base64
        decoded = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(decoded))
        assert img.size == (224, 224)
    
    @pytest.mark.unit
    def test_encode_image_pil(self):
        """Test encoding PIL image to base64."""
        from maple.backend.policy.base import PolicyBackend
        from PIL import Image
        import numpy as np
        
        class TestBackend(PolicyBackend):
            name = "test"
            IMAGE = "test:latest"
            HF_REPOS = {"v1": "org/model"}
        
        backend = TestBackend()
        
        # Create PIL image
        img = Image.fromarray(np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8))
        
        encoded = backend._encode_image(img)
        
        assert isinstance(encoded, str)
    
    @pytest.mark.unit
    def test_encode_image_base64_passthrough(self):
        """Test that base64 strings pass through unchanged."""
        from maple.backend.policy.base import PolicyBackend
        
        class TestBackend(PolicyBackend):
            name = "test"
            IMAGE = "test:latest"
            HF_REPOS = {"v1": "org/model"}
        
        backend = TestBackend()
        
        original = "already_base64_encoded_string"
        encoded = backend._encode_image(original)
        
        assert encoded == original
    
    @pytest.mark.unit
    def test_get_base_url(self):
        """Test URL generation from handle."""
        from maple.backend.policy.base import PolicyBackend, PolicyHandle
        
        class TestBackend(PolicyBackend):
            name = "test"
            IMAGE = "test:latest"
            HF_REPOS = {"v1": "org/model"}
        
        backend = TestBackend()
        
        handle = PolicyHandle(
            policy_id="test-123",
            backend_name="test",
            version="v1",
            host="127.0.0.1",
            port=50000,
        )
        
        url = backend._get_base_url(handle)
        
        assert url == "http://127.0.0.1:50000"


class TestPolicyHandle:
    """Tests for PolicyHandle dataclass."""
    
    @pytest.mark.unit
    def test_to_dict(self):
        """Test serialization to dict."""
        from maple.backend.policy.base import PolicyHandle
        
        handle = PolicyHandle(
            policy_id="policy-abc",
            backend_name="openvla",
            version="7b",
            host="localhost",
            port=8000,
            container_id="container123",
            device="cuda:0",
        )
        
        d = handle.to_dict()
        
        assert d["policy_id"] == "policy-abc"
        assert d["backend_name"] == "openvla"
        assert d["port"] == 8000
        assert d["device"] == "cuda:0"
    
    @pytest.mark.unit
    def test_from_dict(self):
        """Test deserialization from dict."""
        from maple.backend.policy.base import PolicyHandle
        
        data = {
            "policy_id": "policy-xyz",
            "backend_name": "smolvla",
            "version": "libero",
            "host": "127.0.0.1",
            "port": 9000,
            "container_id": "abc123",
            "device": "cuda:1",
            "model_path": "/path/to/model",
            "metadata": {"key": "value"},
        }
        
        handle = PolicyHandle.from_dict(data)
        
        assert handle.policy_id == "policy-xyz"
        assert handle.backend_name == "smolvla"
        assert handle.metadata == {"key": "value"}


class TestEnvHandle:
    """Tests for EnvHandle dataclass."""
    
    @pytest.mark.unit
    def test_to_dict(self):
        """Test serialization to dict."""
        from maple.backend.envs.base import EnvHandle
        
        handle = EnvHandle(
            env_id="env-abc",
            backend_name="libero",
            host="localhost",
            port=8001,
            container_id="env_container",
            metadata={"task": "libero_10/0"},
        )
        
        d = handle.to_dict()
        
        assert d["env_id"] == "env-abc"
        assert d["backend_name"] == "libero"
        assert d["metadata"]["task"] == "libero_10/0"


class TestPolicyRegistry:
    """Tests for policy backend registry."""
    
    @pytest.mark.unit
    def test_registry_contains_openvla(self):
        """Test that OpenVLA is registered."""
        from maple.backend.registry import POLICY_BACKENDS
        
        assert "openvla" in POLICY_BACKENDS
    
    @pytest.mark.unit
    def test_registry_contains_smolvla(self):
        """Test that SmolVLA is registered."""
        from maple.backend.registry import POLICY_BACKENDS
        
        assert "smolvla" in POLICY_BACKENDS


class TestEnvRegistry:
    """Tests for environment backend registry."""
    
    @pytest.mark.unit
    def test_registry_contains_libero(self):
        """Test that LIBERO is registered."""
        from maple.backend.registry import ENV_BACKENDS
        
        assert "libero" in ENV_BACKENDS


class TestOpenVLABackend:
    """Tests for OpenVLA backend."""
    
    @pytest.mark.unit
    def test_hf_repos(self):
        """Test HuggingFace repo mapping."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        
        backend = OpenVLAPolicy()
        
        assert "7b" in backend._hf_repos
        assert backend._hf_repos["7b"] == "openvla/openvla-7b"
    
    @pytest.mark.unit
    def test_info(self):
        """Test backend info."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        
        backend = OpenVLAPolicy()
        info = backend.info()
        
        assert info["name"] == "openvla"
        assert info["type"] == "policy"
        assert "image" in info["inputs"]
        assert "instruction" in info["inputs"]