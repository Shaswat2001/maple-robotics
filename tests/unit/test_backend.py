"""
Unit tests for maple.backend modules.

Tests cover:
- PolicyBackend base class (image encoding, URL generation)
- PolicyHandle and EnvHandle dataclasses
- Policy and environment registries
- OpenVLA backend specifics
"""

import pytest
from unittest.mock import MagicMock, patch


class TestPolicyHandle:
    """Tests for PolicyHandle dataclass."""
    
    @pytest.mark.unit
    def test_to_dict(self):
        """Test serialization to dictionary."""
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
        """Test deserialization from dictionary."""
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
    
    @pytest.mark.unit
    def test_default_values(self):
        """Test default values for optional fields."""
        from maple.backend.policy.base import PolicyHandle
        
        handle = PolicyHandle(
            policy_id="test",
            backend_name="test",
            version="v1",
            host="localhost",
            port=8000,
        )
        
        assert handle.container_id is None
        assert handle.device is None
        assert handle.model_path is None
        assert handle.metadata == {}


class TestEnvHandle:
    """Tests for EnvHandle dataclass."""
    
    @pytest.mark.unit
    def test_to_dict(self):
        """Test serialization to dictionary."""
        from maple.backend.envs.base import EnvHandle
        
        handle = EnvHandle(
            env_id="env-abc",
            backend_name="libero",
            device="cpu",
            host="localhost",
            port="8001",
            container_id="env_container",
            metadata={"task": "libero_10/0"},
        )
        
        d = handle.to_dict()
        
        assert d["env_id"] == "env-abc"
        assert d["backend_name"] == "libero"
        assert d["metadata"]["task"] == "libero_10/0"
    
    @pytest.mark.unit
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        from maple.backend.envs.base import EnvHandle
        
        data = {
            "env_id": "env-xyz",
            "backend_name": "aloha_sim",
            "device": "cuda:0",
            "host": "127.0.0.1",
            "port": "9001",
            "container_id": "container456",
            "metadata": {"display": ":1"},
        }
        
        handle = EnvHandle.from_dict(data)
        
        assert handle.env_id == "env-xyz"
        assert handle.backend_name == "aloha_sim"


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
    
    @pytest.mark.unit
    def test_registry_keys_are_lowercase(self):
        """Test that registry keys are consistently lowercase."""
        from maple.backend.registry import POLICY_BACKENDS
        
        for key in POLICY_BACKENDS:
            assert key == key.lower(), f"Key '{key}' should be lowercase"


class TestEnvRegistry:
    """Tests for environment backend registry."""
    
    @pytest.mark.unit
    def test_registry_contains_libero(self):
        """Test that LIBERO is registered."""
        from maple.backend.registry import ENV_BACKENDS
        
        assert "libero" in ENV_BACKENDS
    
    @pytest.mark.unit
    def test_registry_keys_are_lowercase(self):
        """Test that registry keys are consistently lowercase."""
        from maple.backend.registry import ENV_BACKENDS
        
        for key in ENV_BACKENDS:
            assert key == key.lower(), f"Key '{key}' should be lowercase"


class TestOpenVLABackend:
    """Tests for OpenVLA backend."""
    
    @pytest.mark.unit
    def test_class_attributes(self):
        """Test OpenVLA backend class attributes."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        
        assert OpenVLAPolicy.name == "openvla"
        assert "7b" in OpenVLAPolicy._hf_repos
        assert OpenVLAPolicy._hf_repos["7b"] == "openvla/openvla-7b"
    
    @pytest.mark.unit
    def test_info_method(self, mock_docker_client):
        """Test backend info method."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        
        backend = OpenVLAPolicy()
        info = backend.info()
        
        assert info["name"] == "openvla"
        assert info["type"] == "policy"
        assert "image" in info["inputs"]
        assert "instruction" in info["inputs"]
        assert "action" in info["outputs"]
    
    @pytest.mark.unit
    def test_hf_repos_versions(self, mock_docker_client):
        """Test HuggingFace repository version mapping."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        
        backend = OpenVLAPolicy()
        
        # Check available versions
        assert "7b" in backend._hf_repos
        assert "latest" in backend._hf_repos
        
        # Both should point to same repo
        assert backend._hf_repos["latest"] == backend._hf_repos["7b"]


class TestPolicyBackendBase:
    """Tests for PolicyBackend base class methods."""
    
    @pytest.mark.unit
    def test_get_base_url(self, mock_docker_client):
        """Test URL generation from handle."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        from maple.backend.policy.base import PolicyHandle
        
        backend = OpenVLAPolicy()
        
        handle = PolicyHandle(
            policy_id="test-123",
            backend_name="openvla",
            version="7b",
            host="127.0.0.1",
            port=50000,
        )
        
        url = backend._get_base_url(handle)
        
        assert url == "http://127.0.0.1:50000"
    
    @pytest.mark.unit
    def test_encode_image_base64_passthrough(self, mock_docker_client):
        """Test that base64 strings pass through unchanged."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        
        backend = OpenVLAPolicy()
        
        original = "already_base64_encoded_string"
        encoded = backend._encode_image(original)
        
        assert encoded == original
    
    @pytest.mark.unit
    def test_encode_image_numpy(self, mock_docker_client, sample_image_b64):
        """Test encoding numpy array to base64."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        import numpy as np
        import base64
        from PIL import Image
        import io
        
        backend = OpenVLAPolicy()
        
        # Create numpy image
        img_array = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        
        encoded = backend._encode_image(img_array)
        
        assert isinstance(encoded, str)
        # Should be valid base64
        decoded = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(decoded))
        assert img.size == (224, 224)
    
    @pytest.mark.unit
    def test_encode_image_pil(self, mock_docker_client):
        """Test encoding PIL Image to base64."""
        from maple.backend.policy.openvla import OpenVLAPolicy
        from PIL import Image
        import numpy as np
        
        backend = OpenVLAPolicy()
        
        # Create PIL image
        img = Image.fromarray(np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8))
        
        encoded = backend._encode_image(img)
        
        assert isinstance(encoded, str)
