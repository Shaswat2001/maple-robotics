"""
Tests for maple.state.store module.
"""

import pytest
from datetime import datetime


class TestPolicyStore:
    """Tests for policy storage functions."""
    
    @pytest.mark.unit
    def test_add_policy(self, test_db):
        """Test adding a policy."""
        from maple.state import store
        
        store.add_policy(
            name="openvla",
            version="7b",
            path="/path/to/weights",
            repo="openvla/openvla-7b"
        )
        
        policies = store.list_policies()
        assert "openvla:7b" in policies
    
    @pytest.mark.unit
    def test_get_policy(self, test_db):
        """Test getting a policy."""
        from maple.state import store
        
        store.add_policy("test_policy", "v1", "/test/path", "org/repo")
        
        policy = store.get_policy("test_policy", "v1")
        
        assert policy is not None
        assert policy["name"] == "test_policy"
        assert policy["version"] == "v1"
        assert policy["path"] == "/test/path"
        assert policy["repo"] == "org/repo"
    
    @pytest.mark.unit
    def test_get_nonexistent_policy(self, test_db):
        """Test getting a policy that doesn't exist."""
        from maple.state import store
        
        policy = store.get_policy("nonexistent", "v1")
        assert policy is None
    
    @pytest.mark.unit
    def test_remove_policy(self, test_db):
        """Test removing a policy."""
        from maple.state import store
        
        store.add_policy("to_remove", "v1", "/path", "org/repo")
        assert "to_remove:v1" in store.list_policies()
        
        store.remove_policy("to_remove", "v1")
        assert "to_remove:v1" not in store.list_policies()
    
    @pytest.mark.unit
    def test_list_policies(self, test_db):
        """Test listing multiple policies."""
        from maple.state import store
        
        store.add_policy("policy1", "v1", "/p1", "org/p1")
        store.add_policy("policy2", "v2", "/p2", "org/p2")
        store.add_policy("policy1", "v2", "/p1v2", "org/p1")
        
        policies = store.list_policies()
        
        assert len(policies) == 3
        assert "policy1:v1" in policies
        assert "policy1:v2" in policies
        assert "policy2:v2" in policies


class TestEnvStore:
    """Tests for environment storage functions."""
    
    @pytest.mark.unit
    def test_add_env(self, test_db):
        """Test adding an environment."""
        from maple.state import store
        
        store.add_env("libero", "maple/libero:latest")
        
        envs = store.list_envs()
        assert "libero" in envs
    
    @pytest.mark.unit
    def test_get_env(self, test_db):
        """Test getting an environment."""
        from maple.state import store
        
        store.add_env("test_env", "maple/test:v1")
        
        env = store.get_env("test_env")
        
        assert env is not None
        assert env["name"] == "test_env"
        assert env["image"] == "maple/test:v1"
    
    @pytest.mark.unit
    def test_remove_env(self, test_db):
        """Test removing an environment."""
        from maple.state import store
        
        store.add_env("to_remove", "maple/remove:latest")
        assert "to_remove" in store.list_envs()
        
        store.remove_env("to_remove")
        assert "to_remove" not in store.list_envs()


class TestContainerStore:
    """Tests for container storage functions."""
    
    @pytest.mark.unit
    def test_add_container(self, test_db):
        """Test adding a container."""
        from maple.state import store
        
        store.add_container(
            container_id="abc123",
            type="policy",
            name="openvla-7b-xyz",
            backend="openvla",
            host="127.0.0.1",
            port=50000,
            status="ready",
            metadata={"device": "cuda:0"}
        )
        
        containers = store.list_containers(type="policy")
        assert len(containers) == 1
        assert containers[0]["container_id"] == "abc123"
    
    @pytest.mark.unit
    def test_update_container_status(self, test_db):
        """Test updating container status."""
        from maple.state import store
        
        store.add_container(
            container_id="def456",
            type="env",
            name="libero-xyz",
            backend="libero",
            host="127.0.0.1",
            port=50001,
            status="starting"
        )
        
        store.update_container_status("def456", "ready")
        
        containers = store.list_containers(type="env")
        assert containers[0]["status"] == "ready"
    
    @pytest.mark.unit
    def test_remove_container(self, test_db):
        """Test removing a container."""
        from maple.state import store
        
        store.add_container(
            container_id="ghi789",
            type="policy",
            name="test",
            backend="test",
            host="127.0.0.1",
            port=50002,
            status="ready"
        )
        
        store.remove_container("ghi789")
        
        containers = store.list_containers()
        assert len(containers) == 0
    
    @pytest.mark.unit
    def test_clear_containers(self, test_db):
        """Test clearing all containers."""
        from maple.state import store
        
        store.add_container("c1", "policy", "n1", "b1", "h", 1, "ready")
        store.add_container("c2", "env", "n2", "b2", "h", 2, "ready")
        
        store.clear_containers()
        
        assert len(store.list_containers()) == 0


class TestRunStore:
    """Tests for run history storage functions."""
    
    @pytest.mark.unit
    def test_add_run(self, test_db):
        """Test adding a run."""
        from maple.state import store
        
        store.add_run(
            run_id="run-001",
            policy_id="openvla-7b-abc",
            env_id="libero-xyz",
            task="libero_10/0",
            instruction="Pick up the block"
        )
        
        run = store.get_run("run-001")
        
        assert run is not None
        assert run["policy_id"] == "openvla-7b-abc"
        assert run["task"] == "libero_10/0"
    
    @pytest.mark.unit
    def test_finish_run(self, test_db):
        """Test finishing a run."""
        from maple.state import store
        
        store.add_run(
            run_id="run-002",
            policy_id="p1",
            env_id="e1",
            task="task1",
            instruction="test"
        )
        
        store.finish_run(
            run_id="run-002",
            steps=150,
            total_reward=1.0,
            success=True,
            terminated=True,
            truncated=False,
            video_path="/path/to/video.mp4"
        )
        
        run = store.get_run("run-002")
        
        assert run["steps"] == 150
        assert run["total_reward"] == 1.0
        assert run["success"] == True
        assert run["video_path"] == "/path/to/video.mp4"
    
    @pytest.mark.unit
    def test_list_runs(self, test_db):
        """Test listing runs with filters."""
        from maple.state import store
        
        store.add_run("r1", "policy-a", "env-1", "task1", "inst1")
        store.add_run("r2", "policy-a", "env-1", "task2", "inst2")
        store.add_run("r3", "policy-b", "env-1", "task1", "inst3")
        
        # Filter by policy
        runs = store.list_runs(policy_id="policy-a")
        assert len(runs) == 2
        
        # Filter by task
        runs = store.list_runs(task="task1")
        assert len(runs) == 2
    
    @pytest.mark.unit
    def test_get_run_stats(self, test_db):
        """Test getting run statistics."""
        from maple.state import store
        
        # Add some completed runs
        for i in range(5):
            run_id = f"stat-run-{i}"
            store.add_run(run_id, "policy-stats", "env-1", "task1", "inst")
            store.finish_run(
                run_id=run_id,
                steps=100 + i * 10,
                total_reward=0.5 + (i * 0.1),
                success=(i % 2 == 0),  # 3 successes, 2 failures
                terminated=True,
                truncated=False
            )
        
        stats = store.get_run_stats(policy_id="policy-stats")
        
        assert stats["total_runs"] == 5
        assert stats["successful_runs"] == 3
        assert stats["success_rate"] == 0.6
        assert stats["avg_steps"] == 120.0  # (100+110+120+130+140)/5
