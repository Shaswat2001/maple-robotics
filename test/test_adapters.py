"""
Tests for maple.adapters module.
"""

import pytest
import numpy as np

class TestAdapterRegistry:
    """Tests for adapter registry functions."""
    
    @pytest.mark.unit
    def test_get_adapter_exact_match(self):
        """Test getting adapter with exact match."""
        from maple.adapters import get_adapter
        from maple.adapters.custom import OpenVLALiberoAdapter
        adapter = get_adapter("openvla", "libero")
        assert isinstance(adapter, OpenVLALiberoAdapter)
    
    @pytest.mark.unit
    def test_get_adapter_with_version(self):
        """Test getting adapter when policy has version."""
        from maple.adapters import get_adapter
        from maple.adapters.custom import OpenVLALiberoAdapter
        adapter = get_adapter("openvla:7b", "libero")
        assert isinstance(adapter, OpenVLALiberoAdapter)
    
    @pytest.mark.unit
    def test_get_adapter_fallback(self):
        """Test fallback to identity adapter."""
        from maple.adapters import get_adapter
        adapter = get_adapter("unknown_policy", "unknown_env")
        assert adapter is not None
    
    @pytest.mark.unit
    def test_list_adapters(self):
        """Test listing all adapters."""
        from maple.adapters import list_adapters
        adapters = list_adapters()
        assert isinstance(adapters, dict)
        assert "openvla:libero" in adapters

class TestAdapterBase:
    """Tests for Adapter base class helpers."""
    
    @pytest.mark.unit
    def test_resize_image(self, sample_image_b64):
        """Test image resizing helper."""
        from maple.adapters.base import Adapter
        import base64
        import io
        from PIL import Image
        
        adapter = Adapter()
        image = adapter.decode_image(sample_image_b64)
        resized = adapter.resize_image(image, (64, 64))
        assert resized.size == (64, 64)

class TestOpenVLALiberoAdapter:
    """Tests for OpenVLA-LIBERO adapter."""
    
    @pytest.mark.unit
    def test_transform_obs(self, sample_observation):
        """Test observation transformation."""
        from PIL import Image
        from maple.adapters.custom import OpenVLALiberoAdapter
        adapter = OpenVLALiberoAdapter()
        result = adapter.transform_obs(sample_observation)
        assert "image" in result
        assert isinstance(result["image"], Image.Image)
    
    @pytest.mark.unit
    def test_transform_action(self, sample_action):
        """Test action transformation."""
        from maple.adapters.custom import OpenVLALiberoAdapter
        adapter = OpenVLALiberoAdapter()
        result = adapter.transform_action(sample_action)
        assert isinstance(result, list)
        assert len(result) == 7