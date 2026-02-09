"""
Unit tests for maple.adapters module.

Tests cover:
- Adapter registry lookup (exact match, versioned, fallback)
- Adapter base class helpers (image decoding, resizing)
- OpenVLA-LIBERO adapter observation/action transforms
"""

import pytest
import numpy as np


class TestAdapterRegistry:
    """Tests for adapter registry functions."""
    
    @pytest.mark.unit
    def test_get_adapter_exact_match(self):
        """Test getting adapter with exact policy-env match."""
        from maple.adapters import get_adapter
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = get_adapter("openvla", "libero")
        assert isinstance(adapter, OpenVLALiberoAdapter)
    
    @pytest.mark.unit
    def test_get_adapter_with_version(self):
        """Test getting adapter when policy has version suffix."""
        from maple.adapters import get_adapter
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = get_adapter("openvla:7b", "libero")
        assert isinstance(adapter, OpenVLALiberoAdapter)
    
    @pytest.mark.unit
    def test_get_adapter_fallback(self):
        """Test fallback to identity adapter for unknown pairs."""
        from maple.adapters import get_adapter
        
        adapter = get_adapter("unknown_policy", "unknown_env")
        assert adapter is not None
        # Should be identity adapter
        assert "identity" in adapter.name.lower()
    
    @pytest.mark.unit
    def test_list_adapters(self):
        """Test listing all registered adapters."""
        from maple.adapters import list_adapters
        
        adapters = list_adapters()
        assert isinstance(adapters, dict)
        assert "openvla:libero" in adapters


class TestAdapterBase:
    """Tests for Adapter base class helpers."""
    
    @pytest.mark.unit
    def test_decode_image(self, sample_image_b64):
        """Test decoding base64 image to PIL Image."""
        from maple.adapters.custom import OpenVLALiberoAdapter
        from PIL import Image
        
        # Use a concrete adapter implementation for testing base methods
        adapter = OpenVLALiberoAdapter()
        image = adapter.decode_image(sample_image_b64)
        
        assert isinstance(image, Image.Image)
        assert image.size == (224, 224)
    
    @pytest.mark.unit
    def test_resize_image(self, sample_image_b64):
        """Test image resizing helper."""
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = OpenVLALiberoAdapter()
        image = adapter.decode_image(sample_image_b64)
        resized = adapter.resize_image(image, (64, 64))
        
        assert resized.size == (64, 64)


class TestOpenVLALiberoAdapter:
    """Tests for OpenVLA-LIBERO adapter."""
    
    @pytest.mark.unit
    def test_adapter_attributes(self):
        """Test adapter has required attributes."""
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = OpenVLALiberoAdapter()
        
        assert adapter.name == "openvla:libero"
        assert adapter.policy == "openvla"
        assert adapter.env == "libero"
        assert adapter.image_size == (224, 224)
    
    @pytest.mark.unit
    def test_transform_obs(self, sample_observation):
        """Test observation transformation for OpenVLA."""
        from PIL import Image
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = OpenVLALiberoAdapter()
        result = adapter.transform_obs(sample_observation)
        
        assert "image" in result
        assert isinstance(result["image"], Image.Image)
    
    @pytest.mark.unit
    def test_transform_action(self, sample_action):
        """Test action transformation from OpenVLA format."""
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = OpenVLALiberoAdapter()
        result = adapter.transform_action(sample_action)
        
        assert isinstance(result, list)
        assert len(result) == 7
    
    @pytest.mark.unit
    def test_action_gripper_normalization(self):
        """Test that gripper action is properly normalized."""
        from maple.adapters.custom import OpenVLALiberoAdapter
        
        adapter = OpenVLALiberoAdapter()
        
        # Test with action where gripper = 1.0 (open)
        action = [0.01, -0.02, 0.05, 0.001, 0.002, 0.003, 1.0]
        result = adapter.transform_action(action)
        
        assert len(result) == 7
        # Gripper should be inverted and normalized to -1 or 1
        assert result[-1] == -1.0 or result[-1] == 1.0
