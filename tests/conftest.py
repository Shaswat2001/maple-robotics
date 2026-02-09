"""
Pytest configuration and shared fixtures for Maple tests.

This module provides:
- Custom markers for test categorization
- Shared fixtures for test isolation
- Automatic Docker availability detection
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Pytest Hooks and Configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (require Docker)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests"
    )
    config.addinivalue_line(
        "markers", "gpu: Tests requiring GPU"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if Docker is not available."""
    try:
        import docker
        docker.from_env().ping()
        docker_available = True
    except Exception:
        docker_available = False

    skip_integration = pytest.mark.skip(reason="Docker not available")
    skip_gpu = pytest.mark.skip(reason="GPU not available")

    # Check GPU availability
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        gpu_available = False

    for item in items:
        if "integration" in item.keywords and not docker_available:
            item.add_marker(skip_integration)
        if "gpu" in item.keywords and not gpu_available:
            item.add_marker(skip_gpu)


# =============================================================================
# Directory and Path Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files.
    
    Yields:
        Path: Path to temporary directory, cleaned up after test.
    """
    tmpdir = tempfile.mkdtemp(prefix="maple_test_")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_config_dir(temp_dir, monkeypatch):
    """Create a temporary config directory and patch Path.home().
    
    Args:
        temp_dir: Temporary directory fixture
        monkeypatch: Pytest monkeypatch fixture
        
    Yields:
        Path: Path to .maple config directory
    """
    config_dir = temp_dir / ".maple"
    config_dir.mkdir(parents=True)
    
    # Patch home directory for config
    monkeypatch.setenv("HOME", str(temp_dir))
    
    yield config_dir


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def default_config():
    """Get a fresh default config instance.
    
    Returns:
        Config: Default configuration object
    """
    from maple.utils.config import Config
    return Config()


@pytest.fixture
def config_file(temp_config_dir):
    """Create a test config file.
    
    Args:
        temp_config_dir: Temporary config directory fixture
        
    Returns:
        Path: Path to created config file
    """
    config_path = temp_config_dir / "config.yaml"
    config_content = """
logging:
  level: DEBUG
  verbose: true

daemon:
  port: 9999

policy:
  default_device: cuda:1

eval:
  max_steps: 100
"""
    config_path.write_text(config_content)
    return config_path


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing without Docker.
    
    Yields:
        MagicMock: Mocked Docker client with common operations
    """
    with patch("docker.from_env") as mock:
        client = MagicMock()
        mock.return_value = client
        
        # Mock image operations
        client.images.pull.return_value = MagicMock()
        client.images.get.return_value = MagicMock()
        
        # Mock container operations
        container = MagicMock()
        container.id = "test_container_123"
        container.status = "running"
        container.attrs = {
            "NetworkSettings": {
                "Ports": {"8000/tcp": [{"HostPort": "50000"}]}
            }
        }
        client.containers.run.return_value = container
        client.containers.get.return_value = container
        
        yield client


@pytest.fixture
def mock_requests():
    """Mock requests library for HTTP testing.
    
    Yields:
        dict: Dictionary with 'get' and 'post' mock objects
    """
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Default successful responses
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"status": "ok"}
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "ok"}
        
        yield {"get": mock_get, "post": mock_post}


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_image_b64():
    """Generate a sample base64-encoded image.
    
    Returns:
        str: Base64-encoded PNG image (224x224 RGB)
    """
    import base64
    import io
    from PIL import Image
    import numpy as np
    
    # Create a simple 224x224 RGB image
    img_array = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@pytest.fixture
def sample_observation(sample_image_b64):
    """Generate a sample LIBERO-style observation.
    
    Args:
        sample_image_b64: Base64 image fixture
        
    Returns:
        dict: Observation dictionary with images and robot state
    """
    return {
        "agentview_image": {
            "type": "image",
            "data": sample_image_b64,
            "shape": [224, 224, 3],
            "dtype": "uint8",
        },
        "robot0_eye_in_hand_image": {
            "type": "image",
            "data": sample_image_b64,
            "shape": [224, 224, 3],
            "dtype": "uint8",
        },
        "robot0_joint_pos": {
            "type": "array",
            "data": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            "shape": [7],
            "dtype": "float32",
        },
        "robot0_gripper_qpos": {
            "type": "array",
            "data": [0.04, 0.04],
            "shape": [2],
            "dtype": "float32",
        },
    }


@pytest.fixture
def sample_action():
    """Generate a sample action vector.
    
    Returns:
        list: 7-DOF action [dx, dy, dz, drx, dry, drz, gripper]
    """
    return [0.01, -0.02, 0.05, 0.001, 0.002, 0.003, 1.0]


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def test_db(temp_dir, monkeypatch):
    """Create a test SQLite database.
    
    Args:
        temp_dir: Temporary directory fixture
        monkeypatch: Pytest monkeypatch fixture
        
    Yields:
        Path: Path to test database file
    """
    db_path = temp_dir / "test_state.db"
    monkeypatch.setattr("maple.state.store.DB_FILE", db_path)
    
    # Initialize the database
    from maple.state import store
    store.init_db()
    
    yield db_path
