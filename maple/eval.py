import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from maple.utils.logging import get_logger
from maple.state import store
from maple.config import config

log = get_logger("eval")

@dataclass
class EvalResult:
    """Result of a single evaluation episode."""
    run_id: str
    policy_id: str
    env_id: str
    task: str
    instruction: str
    seed: int
    
    # Outcomes
    steps: int = 0
    total_reward: float = 0.0
    success: bool = False
    terminated: bool = False
    truncated: bool = False
    
    # Timing
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_seconds: float = 0.0
    
    # Optional
    video_path: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "EvalResult":
        return cls(**d)

@dataclass
class BatchResults:
    """Aggregated results from a batch evaluation."""
    batch_id: str
    policy_id: str
    env_id: str
    
    # Config
    tasks: List[str] = field(default_factory=list)
    seeds: List[int] = field(default_factory=list)
    max_steps: int = 300
    
    # Results
    results: List[EvalResult] = field(default_factory=list)
    
    # Timing
    started_at: float = 0.0
    finished_at: float = 0.0
    
    # Computed stats (filled by compute_stats)
    total_episodes: int = 0
    successful_episodes: int = 0
    failed_episodes: int = 0
    error_episodes: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_steps: float = 0.0
    avg_duration: float = 0.0
    
    # Per-task stats
    task_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def compute_stats(self):
        """Compute aggregate statistics from results."""
        if not self.results:
            return
        
        self.total_episodes = len(self.results)
        self.successful_episodes = sum(1 for r in self.results if r.success)
        self.error_episodes = sum(1 for r in self.results if r.error)
        self.failed_episodes = self.total_episodes - self.successful_episodes - self.error_episodes
        
        valid_results = [r for r in self.results if not r.error]
        if valid_results:
            self.success_rate = self.successful_episodes / len(valid_results)
            self.avg_reward = sum(r.total_reward for r in valid_results) / len(valid_results)
            self.avg_steps = sum(r.steps for r in valid_results) / len(valid_results)
            self.avg_duration = sum(r.duration_seconds for r in valid_results) / len(valid_results)
        
        # Per-task stats
        task_results: Dict[str, List[EvalResult]] = {}
        for r in self.results:
            if r.task not in task_results:
                task_results[r.task] = []
            task_results[r.task].append(r)
        
        for task, results in task_results.items():
            valid = [r for r in results if not r.error]
            if valid:
                self.task_stats[task] = {
                    "total": len(results),
                    "successful": sum(1 for r in results if r.success),
                    "success_rate": sum(1 for r in valid if r.success) / len(valid),
                    "avg_reward": sum(r.total_reward for r in valid) / len(valid),
                    "avg_steps": sum(r.steps for r in valid) / len(valid),
                }
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [r.to_dict() if isinstance(r, EvalResult) else r for r in self.results]
        return d
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, path: Path):
        """Save results to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            f.write(self.to_json())
        
        log.info(f"Results saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "BatchResults":
        """Load results from JSON file."""
        with open(path) as f:
            data = json.load(f)
        
        data["results"] = [EvalResult.from_dict(r) for r in data.get("results", [])]
        return cls(**data)
    
    def summary(self) -> str:
        """Generate a summary string."""
        lines = [
            f"Batch Evaluation Results: {self.batch_id}",
            f"=" * 50,
            f"Policy: {self.policy_id}",
            f"Environment: {self.env_id}",
            f"Tasks: {len(self.tasks)} | Seeds: {len(self.seeds)}",
            f"",
            f"Overall Results:",
            f"  Episodes: {self.total_episodes}",
            f"  Success Rate: {self.success_rate:.1%}",
            f"  Avg Reward: {self.avg_reward:.3f}",
            f"  Avg Steps: {self.avg_steps:.1f}",
            f"  Avg Duration: {self.avg_duration:.2f}s",
            f"",
        ]
        
        if self.task_stats:
            lines.append("Per-Task Results:")
            for task, stats in sorted(self.task_stats.items()):
                lines.append(
                    f"  {task}: {stats['success_rate']:.1%} "
                    f"({stats['successful']}/{stats['total']}) "
                    f"reward={stats['avg_reward']:.3f}"
                )
        
        if self.error_episodes > 0:
            lines.append(f"\nErrors: {self.error_episodes} episodes failed with errors")
        
        return "\n".join(lines)

class BatchEvaluator:
    """
    Runs batch evaluations across tasks and seeds.
    
    Communicates with daemon to run episodes.
    """
    
    def __init__(
        self,
        daemon_url: str = "http://127.0.0.1:8000",
    ):
        self.daemon_url = daemon_url.rstrip("/")
        self._session = None
    
    @property
    def session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session
    
    def _daemon_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make request to daemon."""
        import requests
        
        url = f"{self.daemon_url}{endpoint}"
        resp = self.session.request(method, url, **kwargs)
        
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Daemon error ({resp.status_code}): {detail}")
        
        return resp.json()
    
    def run_single(
        self,
        policy_id: str,
        env_id: str,
        task: str,
        instruction: Optional[str] = None,
        seed: int = 0,
        max_steps: int = 300,
        timeout: int = 200,
        unnorm_key: Optional[str] = None,
        save_video: bool = False,
        video_path: Optional[str] = None,
    ) -> EvalResult:
        """Run a single evaluation episode."""
        
        run_id = f"eval-{uuid.uuid4().hex[:8]}"
        started_at = time.time()
        result = EvalResult(
            run_id=run_id,
            policy_id=policy_id,
            env_id=env_id,
            task=task,
            instruction=instruction or "",
            seed=seed,
            started_at=started_at,
        )
        
        try:
            # Call daemon /run endpoint
            response = self._daemon_request(
                "POST",
                "/run",
                json={
                    "policy_id": policy_id,
                    "env_id": env_id,
                    "task": task,
                    "instruction": instruction,
                    "max_steps": max_steps,
                    "seed": seed,
                    "unnorm_key": unnorm_key,
                    "save_video": save_video,
                    "video_path": video_path,
                },
                timeout=max_steps * timeout,  # Generous timeout
            )
            
            result.steps = response.get("steps", 0)
            result.total_reward = response.get("total_reward", 0.0)
            result.success = response.get("success", False)
            result.terminated = response.get("terminated", False)
            result.truncated = response.get("truncated", False)
            result.video_path = response.get("video_path")
            result.instruction = response.get("instruction", instruction or "")
            
        except Exception as e:
            log.error(f"Episode failed: {task} seed={seed}: {e}")
            result.error = str(e)
        
        result.finished_at = time.time()
        result.duration_seconds = result.finished_at - result.started_at
        
        # Store in database
        store.add_run(
            run_id=run_id,
            policy_id=policy_id,
            env_id=env_id,
            task=task,
            instruction=result.instruction,
            metadata={"seed": seed},
        )
        
        if not result.error:
            store.finish_run(
                run_id=run_id,
                steps=result.steps,
                total_reward=result.total_reward,
                success=result.success,
                terminated=result.terminated,
                truncated=result.truncated,
                video_path=result.video_path,
            )
        
        return result
    
    def run(
        self,
        policy_id: str,
        env_id: str,
        tasks: List[str],
        seeds: List[int] = None,
        max_steps: int = 300,
        timeout: int = 200,
        unnorm_key: Optional[str] = None,
        save_video: bool = False,
        video_dir: Optional[str] = None,
        parallel: int = 1,
        progress_callback: Optional[Callable[[int, int, EvalResult], None]] = None,
    ) -> BatchResults:
        """
        Run batch evaluation.
        
        Args:
            policy_id: ID of served policy
            env_id: ID of served environment
            tasks: List of task names
            seeds: List of seeds (default: [0])
            max_steps: Max steps per episode
            unnorm_key: Action unnormalization key
            save_video: Whether to save videos
            video_dir: Directory for videos
            parallel: Number of parallel evaluations (1 = sequential)
            progress_callback: Called after each episode with (completed, total, result)
        
        Returns:
            BatchResults with all episodes
        """
        seeds = seeds or [0]
        video_dir = Path(video_dir or config.eval.video_dir).expanduser()
        
        batch_id = f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        batch = BatchResults(
            batch_id=batch_id,
            policy_id=policy_id,
            env_id=env_id,
            tasks=tasks,
            seeds=seeds,
            max_steps=max_steps,
            started_at=time.time(),
        )
        
        # Build episode list
        episodes = []
        for task in tasks:
            for seed in seeds:
                video_path = None
                if save_video:
                    video_path = str(video_dir / f"{batch_id}_{task.replace('/', '_')}_s{seed}.mp4")
                
                episodes.append({
                    "policy_id": policy_id,
                    "env_id": env_id,
                    "task": task,
                    "seed": seed,
                    "max_steps": max_steps,
                    "unnorm_key": unnorm_key,
                    "save_video": save_video,
                    "video_path": video_path,
                })
        
        total = len(episodes)
        completed = 0
        
        log.info(f"Starting batch evaluation: {total} episodes ({len(tasks)} tasks × {len(seeds)} seeds)")
        
        if parallel <= 1:
            # Sequential execution
            for ep in episodes:
                result = self.run_single(**ep, timeout= timeout)
                batch.results.append(result)
                completed += 1
                
                status = "✓" if result.success else ("✗" if not result.error else "!")
                log.info(f"[{completed}/{total}] {status} {ep['task']} seed={ep['seed']} reward={result.total_reward:.3f}")
                
                if progress_callback:
                    progress_callback(completed, total, result)
        else:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                futures = {
                    executor.submit(self.run_single, **ep): ep
                    for ep in episodes
                }
                
                for future in as_completed(futures):
                    ep = futures[future]
                    result = future.result()
                    batch.results.append(result)
                    completed += 1
                    
                    status = "✓" if result.success else ("✗" if not result.error else "!")
                    log.info(f"[{completed}/{total}] {status} {ep['task']} seed={ep['seed']} reward={result.total_reward:.3f}")
                    
                    if progress_callback:
                        progress_callback(completed, total, result)
        
        batch.finished_at = time.time()
        batch.compute_stats()
        
        log.info(f"Batch complete: {batch.success_rate:.1%} success rate")
        
        return batch

def format_results_markdown(batch: BatchResults) -> str:
    """Format batch results as markdown."""
    lines = [
        f"# Evaluation Results: {batch.batch_id}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Policy | `{batch.policy_id}` |",
        f"| Environment | `{batch.env_id}` |",
        f"| Total Episodes | {batch.total_episodes} |",
        f"| Success Rate | {batch.success_rate:.1%} |",
        f"| Avg Reward | {batch.avg_reward:.3f} |",
        f"| Avg Steps | {batch.avg_steps:.1f} |",
        f"| Duration | {batch.finished_at - batch.started_at:.1f}s |",
        "",
    ]
    
    if batch.task_stats:
        lines.extend([
            "## Per-Task Results",
            "",
            "| Task | Success Rate | Avg Reward | Avg Steps |",
            "|------|--------------|------------|-----------|",
        ])
        
        for task, stats in sorted(batch.task_stats.items()):
            lines.append(
                f"| {task} | {stats['success_rate']:.1%} | {stats['avg_reward']:.3f} | {stats['avg_steps']:.1f} |"
            )
        lines.append("")
    
    if batch.error_episodes > 0:
        lines.extend([
            "## Errors",
            "",
            f"{batch.error_episodes} episodes failed with errors:",
            "",
        ])
        for r in batch.results:
            if r.error:
                lines.append(f"- `{r.task}` seed={r.seed}: {r.error}")
        lines.append("")
    
    return "\n".join(lines)

def format_results_csv(batch: BatchResults) -> str:
    """Format batch results as CSV."""
    lines = [
        "run_id,task,seed,success,reward,steps,duration,error"
    ]
    
    for r in batch.results:
        lines.append(
            f"{r.run_id},{r.task},{r.seed},{r.success},{r.total_reward:.4f},"
            f"{r.steps},{r.duration_seconds:.2f},{r.error or ''}"
        )
    
    return "\n".join(lines)
