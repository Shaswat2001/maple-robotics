"""
Batch evaluation system for MAPLE.

This module provides tools for running large-scale evaluations of policies
across multiple tasks and random seeds. It handles parallel execution,
result aggregation, statistics computation, and output formatting.

Key features:
- Single and batch episode execution
- Parallel evaluation with configurable workers
- Comprehensive result tracking and statistics
- Per-task performance breakdown
- Multiple output formats (JSON, Markdown, CSV)
- Progress tracking with callbacks
- Database integration for result persistence

The evaluation system communicates with the MAPLE daemon to execute episodes
and aggregates results into structured formats for analysis and reporting.
"""

import json
import time
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from maple.state import store
from maple.utils.config import get_config
from maple.utils.logging import get_logger

log = get_logger("eval")

@dataclass
class EvalResult:
    """
    Result container for a single evaluation episode.
    
    Stores all information about an episode execution including outcomes,
    timing, and optional error information. Provides serialization for
    persistence and reporting.
    """
    
    run_id: str
    policy_id: str
    env_id: str
    task: str
    instruction: str
    seed: int
    
    # Episode outcomes
    steps: int = 0
    total_reward: float = 0.0
    success: bool = False
    terminated: bool = False
    truncated: bool = False
    
    # Timing information
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_seconds: float = 0.0
    
    # Optional data
    video_path: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """
        Convert result to dictionary representation.
        
        :return: Dictionary containing all result fields.
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "EvalResult":
        """
        Create result from dictionary representation.
        
        :param d: Dictionary containing result fields.
        
        :return: EvalResult instance reconstructed from dictionary.
        """
        return cls(**d)

@dataclass
class BatchResults:
    """
    Aggregated results from a batch evaluation.
    
    Container for multiple episode results with automatic statistics
    computation. Provides per-task breakdowns, success rates, and
    timing information. Supports multiple serialization formats for
    reporting and analysis.
    """
    
    batch_id: str
    policy_id: str
    env_id: str
    
    # Configuration
    tasks: List[str] = field(default_factory=list)
    seeds: List[int] = field(default_factory=list)
    max_steps: int = 300
    
    # Episode results
    results: List[EvalResult] = field(default_factory=list)
    
    # Timing
    started_at: float = 0.0
    finished_at: float = 0.0
    
    # Computed statistics (filled by compute_stats)
    total_episodes: int = 0
    successful_episodes: int = 0
    failed_episodes: int = 0
    error_episodes: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_steps: float = 0.0
    avg_duration: float = 0.0
    
    # Per-task breakdown
    task_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def compute_stats(self):
        """
        Compute aggregate statistics from episode results.
        
        Calculates overall metrics (success rate, averages) and per-task
        breakdowns. Should be called after all episodes are complete.
        Handles errors gracefully by excluding error episodes from averages.
        """
        if not self.results:
            return
        
        # Overall counts
        self.total_episodes = len(self.results)
        self.successful_episodes = sum(1 for r in self.results if r.success)
        self.error_episodes = sum(1 for r in self.results if r.error)
        self.failed_episodes = self.total_episodes - self.successful_episodes - self.error_episodes
        
        # Compute averages excluding error episodes
        valid_results = [r for r in self.results if not r.error]
        if valid_results:
            self.success_rate = self.successful_episodes / len(valid_results)
            self.avg_reward = sum(r.total_reward for r in valid_results) / len(valid_results)
            self.avg_steps = sum(r.steps for r in valid_results) / len(valid_results)
            self.avg_duration = sum(r.duration_seconds for r in valid_results) / len(valid_results)
        
        # Group results by task
        task_results: Dict[str, List[EvalResult]] = {}
        for r in self.results:
            if r.task not in task_results:
                task_results[r.task] = []
            task_results[r.task].append(r)
        
        # Compute per-task statistics
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
        """
        Convert batch results to dictionary representation.
        
        :return: Dictionary containing all batch data including nested results.
        """
        d = asdict(self)
        # Ensure EvalResult objects are converted to dicts
        d["results"] = [r.to_dict() if isinstance(r, EvalResult) else r for r in self.results]
        return d
    
    def to_json(self, indent: int = 2) -> str:
        """
        Convert batch results to JSON string.
        
        :param indent: Indentation level for pretty printing.
        :return: JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, path: Path):
        """
        Save batch results to JSON file.
        
        Creates parent directories if needed. The saved file contains
        complete batch data including all episode results and statistics.
        
        :param path: Destination file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            f.write(self.to_json())
        
        log.info(f"Results saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "BatchResults":
        """
        Load batch results from JSON file.
        
        Reconstructs BatchResults object from saved JSON, including
        all nested EvalResult objects.
        
        :param path: Path to JSON file.
        :return: Reconstructed BatchResults instance.
        """
        with open(path) as f:
            data = json.load(f)
        
        # Reconstruct EvalResult objects
        data["results"] = [EvalResult.from_dict(r) for r in data.get("results", [])]
        return cls(**data)
    
    def summary(self) -> str:
        """
        Generate a human-readable summary string.
        
        Creates a formatted text summary with overall statistics and
        per-task breakdowns. Suitable for console output or reports.
        
        :return: Multi-line summary string.
        """
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
        
        # Add per-task breakdown if available
        if self.task_stats:
            lines.append("Per-Task Results:")
            for task, stats in sorted(self.task_stats.items()):
                lines.append(
                    f"  {task}: {stats['success_rate']:.1%} "
                    f"({stats['successful']}/{stats['total']}) "
                    f"reward={stats['avg_reward']:.3f}"
                )
        
        # Note any errors
        if self.error_episodes > 0:
            lines.append(f"\nErrors: {self.error_episodes} episodes failed with errors")
        
        return "\n".join(lines)

class BatchEvaluator:
    """
    Orchestrator for batch evaluations.
    
    Manages the execution of multiple evaluation episodes across tasks and
    seeds, communicating with the MAPLE daemon to run individual episodes.
    Supports both sequential and parallel execution with progress tracking.
    
    The evaluator:
    - Builds episode lists from task/seed combinations
    - Executes episodes via daemon HTTP API
    - Aggregates results with statistics
    - Persists results to database
    - Provides progress callbacks
    """
    
    def __init__(
        self,
        daemon_url: str = "http://127.0.0.1:8000",
    ):
        """
        Initialize the batch evaluator.
        
        :param daemon_url: URL of the MAPLE daemon (default: localhost:8000).
        """
        self.daemon_url = daemon_url.rstrip("/")
        self._session = None
    
    @property
    def session(self):
        """
        Lazy-initialized requests session.
        
        Creates a persistent HTTP session for connection pooling
        across multiple requests to the daemon.
        
        :return: Requests session instance.
        """
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session
    
    def _daemon_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Make HTTP request to daemon API.
        
        Handles request execution and error processing. Raises detailed
        errors on non-200 responses.
        
        :param method: HTTP method (GET, POST, etc.).
        :param endpoint: API endpoint path (e.g., '/run').
        :param kwargs: Additional arguments for requests (json, timeout, etc.).
        
        :return: JSON response from daemon.
        
        """
        import requests
        
        url = f"{self.daemon_url}{endpoint}"
        resp = self.session.request(method, url, **kwargs)
        
        # Handle errors
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
        env_kwargs: Optional[Dict[str, Any]] = {},
        model_kwargs: Optional[Dict[str, Any]] = {},
        save_video: bool = False,
        video_path: Optional[str] = None,
    ) -> EvalResult:
        """
        Run a single evaluation episode.
        
        Executes one episode via the daemon /run endpoint and packages
        the results into an EvalResult. Handles errors gracefully by
        storing error information in the result rather than raising.
        
        Also persists the result to the database for tracking.
        
        :param policy_id: Policy container ID to use.
        :param env_id: Environment container ID to use.
        :param task: Task specification to execute.
        :param instruction: Optional instruction override.
        :param seed: Random seed for reproducibility.
        :param max_steps: Maximum steps before truncation.
        :param timeout: Timeout multiplier for HTTP request.
        :param env_kwargs: Env-specific parameters.
        :param model_kwargs: Model-specific parameters.
        :param save_video: Whether to record video.
        :param video_path: Optional path for video output.
        :return: EvalResult with episode outcomes and metrics.
        """
        # Generate unique run ID
        run_id = f"eval-{uuid.uuid4().hex[:8]}"
        started_at = time.time()
        
        # Initialize result container
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
            # Call daemon to execute episode
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
                    "env_kwargs": env_kwargs,
                    "model_kwargs": model_kwargs,
                    "save_video": save_video,
                    "video_path": video_path,
                },
                timeout=max_steps * timeout,  # Generous timeout for episode
            )
            
            # Extract results from response
            result.steps = response.get("steps", 0)
            result.total_reward = response.get("total_reward", 0.0)
            result.success = response.get("success", False)
            result.terminated = response.get("terminated", False)
            result.truncated = response.get("truncated", False)
            result.video_path = response.get("video_path")
            result.instruction = response.get("instruction", instruction or "")
            
        except Exception as e:
            # Store error but don't raise - allow batch to continue
            log.error(f"Episode failed: {task} seed={seed}: {e}")
            result.error = str(e)
        
        # Record timing
        result.finished_at = time.time()
        result.duration_seconds = result.finished_at - result.started_at
        
        # Persist to database
        store.add_run(
            run_id=run_id,
            policy_id=policy_id,
            env_id=env_id,
            task=task,
            instruction=result.instruction,
            metadata={"seed": seed},
        )
        
        # Update with final results if no error
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
        env_kwargs: Optional[Dict[str, Any]] = {},
        model_kwargs: Optional[Dict[str, Any]] = {},
        save_video: bool = False,
        video_dir: Optional[str] = None,
        parallel: int = 1,
        progress_callback: Optional[Callable[[int, int, EvalResult], None]] = None,
    ) -> BatchResults:
        """
        Run batch evaluation across multiple tasks and seeds.
        
        Executes all combinations of tasks × seeds, either sequentially or
        in parallel. Aggregates results with statistics and provides
        progress tracking via optional callback.
        
        The total number of episodes executed is len(tasks) × len(seeds).
        Each episode is tracked individually with results stored in the
        database and aggregated in the returned BatchResults.
        
        :param policy_id: Policy container ID to evaluate.
        :param env_id: Environment container ID to use.
        :param tasks: List of task specifications to evaluate.
        :param seeds: List of random seeds (default: [0]).
        :param max_steps: Maximum steps per episode.
        :param timeout: Timeout multiplier for HTTP requests.
        :param env_kwargs: Env-specific parameters.
        :param model_kwargs: Model-specific parameters.
        :param save_video: Whether to record videos.
        :param video_dir: Directory for video files.
        :param parallel: Number of parallel workers (1 = sequential).
        :param progress_callback: Optional callback(completed, total, result).
        :return: BatchResults with all episode results and statistics.
        """
        config = get_config()
        # Use default seed if not specified
        seeds = seeds or [0]
        
        # Resolve video directory
        video_dir = Path(video_dir or config.eval.video_dir).expanduser()
        
        # Generate unique batch ID with timestamp
        batch_id = f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Initialize batch results container
        batch = BatchResults(
            batch_id=batch_id,
            policy_id=policy_id,
            env_id=env_id,
            tasks=tasks,
            seeds=seeds,
            max_steps=max_steps,
            started_at=time.time(),
        )
        
        # Build episode list (cartesian product of tasks × seeds)
        episodes = []
        for task in tasks:
            for seed in seeds:
                # Generate video path if recording enabled
                video_path = None
                if save_video:
                    # Sanitize task name for filename
                    video_path = str(video_dir / f"{batch_id}_{task.replace('/', '_')}_s{seed}.mp4")
                
                episodes.append({
                    "policy_id": policy_id,
                    "env_id": env_id,
                    "task": task,
                    "seed": seed,
                    "max_steps": max_steps,
                    "env_kwargs": env_kwargs,
                    "model_kwargs": model_kwargs,
                    "save_video": save_video,
                    "video_path": video_path,
                })
        
        total = len(episodes)
        completed = 0
        
        log.info(f"Starting batch evaluation: {total} episodes ({len(tasks)} tasks × {len(seeds)} seeds)")
        
        if parallel <= 1:
            # Sequential execution - run one episode at a time
            for ep in episodes:
                result = self.run_single(**ep, timeout=timeout)
                batch.results.append(result)
                completed += 1
                
                # Log status with emoji indicator
                status = "✓" if result.success else ("✗" if not result.error else "!")
                log.info(f"[{completed}/{total}] {status} {ep['task']} seed={ep['seed']} reward={result.total_reward:.3f}")
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, total, result)
        else:
            # Parallel execution - use thread pool
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                # Submit all episodes to executor
                futures = {
                    executor.submit(self.run_single, **ep, timeout=timeout): ep
                    for ep in episodes
                }
                
                # Process results as they complete
                for future in as_completed(futures):
                    ep = futures[future]
                    result = future.result()
                    batch.results.append(result)
                    completed += 1
                    
                    # Log status
                    status = "✓" if result.success else ("✗" if not result.error else "!")
                    log.info(f"[{completed}/{total}] {status} {ep['task']} seed={ep['seed']} reward={result.total_reward:.3f}")
                    
                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(completed, total, result)
        
        # Record completion time
        batch.finished_at = time.time()
        
        # Compute aggregate statistics
        batch.compute_stats()
        
        log.info(f"Batch complete: {batch.success_rate:.1%} success rate")
        
        return batch

def format_results_markdown(batch: BatchResults) -> str:
    """
    Format batch results as Markdown document.
    
    Creates a structured Markdown document with tables for summary
    statistics, per-task results, and error details. Suitable for
    inclusion in reports or documentation.
    
    :param batch: Batch results to format.
    :return: Markdown-formatted string with tables and headers.
    """
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
    
    # Add per-task table if available
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
    
    # Add error section if any errors occurred
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
    """
    Format batch results as CSV data.
    
    Creates a CSV file with one row per episode containing key metrics.
    Suitable for import into spreadsheet software or data analysis tools.
    
    :param batch: Batch results to format.
    :return: CSV-formatted string with header row.
    """
    lines = [
        "run_id,task,seed,success,reward,steps,duration,error"
    ]
    
    # Add one row per episode
    for r in batch.results:
        lines.append(
            f"{r.run_id},{r.task},{r.seed},{r.success},{r.total_reward:.4f},"
            f"{r.steps},{r.duration_seconds:.2f},{r.error or ''}"
        )
    
    return "\n".join(lines)