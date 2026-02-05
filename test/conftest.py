"""
Pytest fixtures for Maple tests.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmpdir = tempfile.mkdtemp(prefix="maple_test_")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)

@pytest.fixture
def temp_config_dir(temp_dir, monkeypatch):
    """Create a temporary config directory and patch Path.home()."""
    config_dir = temp_dir / ".maple"
    config_dir.mkdir(parents=True)
    
    # Patch home directory for config
    monkeypatch.setenv("HOME", str(temp_dir))
    
    yield config_dir

@pytest.fixture
def default_config():
    """Get a fresh default config instance."""
    from maple.utils.config import Config
    return Config()

@pytest.fixture
def config_file(temp_config_dir):
    """Create a test config file."""
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

@pytest.fixture
def mock_docker_client():
    """Mock Docker client."""
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
        container.attrs = {"NetworkSettings": {"Ports": {"8000/tcp": [{"HostPort": "50000"}]}}}
        client.containers.run.return_value = container
        client.containers.get.return_value = container
        
        yield client

@pytest.fixture
def mock_requests():
    """Mock requests library."""
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Default successful responses
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"status": "ok"}
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "ok"}
        
        yield {"get": mock_get, "post": mock_post}

@pytest.fixture
def sample_image_b64():
    """Generate a sample base64-encoded image."""
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
    """Generate a sample LIBERO-style observation."""
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
    """Generate a sample action."""
    return [0.01, -0.02, 0.05, 0.001, 0.002, 0.003, 1.0]

@pytest.fixture
def test_db(temp_dir, monkeypatch):
    """Create a test SQLite database."""
    db_path = temp_dir / "test_state.db"
    monkeypatch.setattr("maple.state.store.DB_FILE", db_path)
    
    # Initialize the database
    from maple.state import store
    store.init_db()
    
    yield db_path

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (require Docker)")
    config.addinivalue_line("markers", "slow: Slow tests")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if Docker is not available."""
    try:
        import docker
        docker.from_env().ping()
        docker_available = True
    except Exception:
        docker_available = False
    
    skip_integration = pytest.mark.skip(reason="Docker not available")
    
    for item in items:
        if "integration" in item.keywords and not docker_available:
            item.add_marker(skip_integration)
