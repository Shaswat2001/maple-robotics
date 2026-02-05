"""
Command-line interface.

This module provides the main CLI application for interacting with MAPLE
(Model and Policy Learning Evaluation). It offers commands for
managing policies, environments, running evaluations, and controlling the
daemon.

Key features:
- Policy and environment management (pull, serve, list)
- Single episode execution with real-time feedback
- Batch evaluation across multiple tasks and seeds
- Daemon control and status monitoring
- Configuration management
- Multiple output formats (JSON, Markdown, CSV)
- Progress tracking with rich console output

The CLI is built with Typer and Rich for a modern command-line experience
with helpful error messages, progress indicators, and formatted output.

Commands:
- pull: Download policies and environments
- serve: Start containers for policies/environments
- list: List available resources
- env: Environment-specific operations
- policy: Policy-specific operations
- config: Configuration management
- run: Execute a single episode
- eval: Run batch evaluations
- status: Check daemon status
- stop: Stop the daemon
"""

import typer 
import requests
from rich import print
from pathlib import Path
from typing import Optional
from rich.progress import Progress, SpinnerColumn, TextColumn

from maple.cmd.cli.misc import daemon_url
from maple.utils.config import get_config, load_config
from maple.utils.logging import setup_logging, get_logger
from maple.utils.eval import BatchEvaluator, format_results_markdown, format_results_csv
from maple.cmd.cli import pull_app, serve_app, list_app, env_app, config_app, policy_app

log = get_logger("cli")

# Initialize the main Typer application
# no_args_is_help=True ensures help is shown when no command is given
app = typer.Typer(no_args_is_help= True)

@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[Path] = typer.Option(None, "--log-file", help="Write logs to file"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """
    Global callback for CLI initialization.
    
    Loads configuration and sets up logging based on command-line options.
    This runs before any command is executed.
    
    :param verbose: Enable verbose (DEBUG level) logging output.
    :param log_file: Path to write logs to file instead of stderr.
    :param config_file: Path to custom configuration file.
    """
    
    # Load configuration from file (or use defaults)
    config = load_config(config_file)
    
    # Override logging settings with CLI args
    # Verbose flag takes precedence over config file
    level = "DEBUG" if verbose else config.logging.level
    log_path = log_file or (Path(config.logging.file) if config.logging.file else None)
    setup_logging(level=level, log_file=log_path, verbose=verbose)

# Register sub-applications for different command groups
# These handle pull, serve, list, env, policy, and config commands
app.add_typer(pull_app, name="pull", help="Download management of envs and policies")
app.add_typer(serve_app, name="serve", help="Spin docker containers")
app.add_typer(list_app, name="list")
app.add_typer(env_app, name="env")
app.add_typer(policy_app, name="policy")
app.add_typer(config_app, name="config", help="Configuration management")

@app.command("run")
def run(
    policy_id: str = typer.Argument(..., help="Policy ID (e.g., openvla-7b-a1b2c3d4)"),
    env_id: str = typer.Argument(..., help="Environment ID (e.g., libero-x1y2z3w4)"),
    task: str = typer.Option(..., "--task", "-t", help="Task spec (e.g., libero_10/0)"),
    instruction: Optional[str] = typer.Option(None, "--instruction", "-i", help="Override task instruction"),
    max_steps: int = typer.Option(None, "--max-steps", "-m", help="Maximum steps per episode"),
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed"),
    unnorm_key: Optional[str] = typer.Option(None, "--unnorm-key", "-u", help="Dataset key for action unnormalization"),
    save_video: bool = typer.Option(False, "--save-video", "-v", help="Save rollout video"),
    video_dir: Optional[str] = typer.Option(None, "--video-path", help="Custom video output path"),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Constant multiplied with the max_steps to determine the timeout"),
    port: int = typer.Option(None, "--port"),
) -> None:
    """
    Run a policy on an environment task.
    
    Executes a single episode of a policy on a specified environment task,
    communicating with the MAPLE daemon to orchestrate the execution. Displays
    real-time progress and results including success status, steps taken,
    rewards, and video paths.
    
    :param policy_id: Identifier of the policy container to use.
    :param env_id: Identifier of the environment container to use.
    :param task: Task specification string.
    :param instruction: Optional instruction to override default task instruction.
    :param max_steps: Maximum number of steps before truncation.
    :param seed: Random seed for reproducibility.
    :param unnorm_key: Dataset key for unnormalizing policy actions.
    :param save_video: Whether to record and save episode video.
    :param video_dir: Directory path for saving videos.
    :param timeout: Timeout multiplier for HTTP request.
    :param port: Daemon port number.
    """
    config = get_config()
    # Use config defaults for any unspecified parameters
    port = port or config.daemon.port
    max_steps = max_steps if max_steps is not None else config.run.max_steps
    timeout = timeout if timeout is not None else config.run.timeout
    save_video = save_video if save_video is not None else config.run.save_video
    video_dir = video_dir or config.run.video_dir
    
    # Build the request payload with required fields
    payload = {
        "policy_id": policy_id,
        "env_id": env_id,
        "task": task,
        "max_steps": max_steps,
        "save_video": save_video,
    }
    
    # Add optional fields only if provided
    if instruction:
        payload["instruction"] = instruction
    if seed is not None:
        payload["seed"] = seed
    if unnorm_key:
        payload["unnorm_key"] = unnorm_key
    if video_dir:
        payload["video_dir"] = video_dir
    
    # Execute the run with a progress indicator
    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task(f"Running policy on task...")
            # Display run configuration
            print(f"  Policy: {policy_id}")
            print(f"  Env: {env_id}")
            print(f"  Task: {task}")
            print(f"  Max steps: {max_steps}")
            
            # Send POST request to daemon with generous timeout
            # Timeout is max_steps * timeout_multiplier to allow long episodes
            r = requests.post(
                f"{daemon_url(port)}/run",
                json=payload,
                timeout=int(max_steps * timeout),
            )
    except requests.exceptions.Timeout:
        # Handle timeout gracefully
        print(f"[red]Error:[/red] Request timed out after {max_steps * timeout}s")
        raise typer.Exit(1)

    # Check for HTTP errors
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)

    result = r.json()
    
    # Display success/failure status
    success = result.get("success", False)
    if success:
        print(f"\n[bold green]✓ Task completed successfully![/bold green]")
    else:
        print(f"\n[yellow]Task finished (not successful)[/yellow]")
    
    # Display detailed results
    print(f"\n[cyan]Results:[/cyan]")
    print(f"  Run ID: {result.get('run_id')}")
    print(f"  Steps: {result.get('steps')}")
    print(f"  Total Reward: {result.get('total_reward', 0):.4f}")
    print(f"  Terminated: {result.get('terminated')}")
    print(f"  Truncated: {result.get('truncated')}")
    
    # Show video path if video was saved
    if result.get("video_path"):
        print(f"  Video saved: {result.get('video_path')}")

@app.command("status")
def status(port: int = typer.Option(None, "--port")) -> None:
    """
    Check MAPLE daemon status.
    
    Queries the daemon to check if it's running and displays status
    information including active containers and configuration.

    :param port: Daemon port number.
    """

    config = get_config()
    # Use config default if port not specified
    port = port or config.daemon.port
    
    try:
        # Try to connect to daemon with short timeout
        r = requests.get(f"http://0.0.0.0:{port}/status", timeout=1)
        data = r.json()
        print("[bold green]MAPLE daemon running[/bold green]")
        print(data)
    except requests.exceptions.ConnectionError:
        # Daemon not reachable
        print("[red]MAPLE daemon not running[/red]")

@app.command("stop")
def stop(port: int = typer.Option(None, "--port")) -> None:
    """
    Stop the MAPLE daemon.
    
    Sends a shutdown request to the daemon, stopping all managed containers
    and terminating the daemon process.
    
    :param port: Daemon port number.
    """

    config = get_config()
    # Use config default if port not specified
    port = port or config.daemon.port
    
    try:
        # Send stop request to daemon
        requests.post(f"{daemon_url(port)}/stop")
        print("[green]MAPLE daemon stopped[/green]")
    except requests.exceptions.ConnectionError:
        # Daemon already stopped or not running
        print("[red]Daemon not running[/red]")

@app.command("eval")
def eval_cmd(
    policy_id: str = typer.Argument(..., help="Policy ID (e.g., openvla-7b-a1b2c3d4)"),
    env_id: str = typer.Argument(..., help="Environment ID (e.g., libero-x1y2z3w4)"),
    backend: str = typer.Argument(..., help="Environment backend name"),
    tasks: str = typer.Option(..., "--tasks", "-t", help="Tasks (comma-separated or suite name like libero_10)"),
    seeds: str = typer.Option("0", "--seeds", "-s", help="Seeds (comma-separated, e.g., 0,1,2)"),
    max_steps: int = typer.Option(None, "--max-steps", "-m", help="Maximum steps per episode"),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Constant multiplied with the max_steps to determine the timeout"),
    unnorm_key: Optional[str] = typer.Option(None, "--unnorm-key", "-u", help="Dataset key for action unnormalization"),
    save_video: bool = typer.Option(None, "--save-video", "-v", help="Save rollout videos"),
    video_dir: Optional[str] = typer.Option(None, "--video-dir", help="Directory for videos"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory for results"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json, markdown, csv"),
    parallel: int = typer.Option(1, "--parallel", "-p", help="Parallel evaluations (experimental)"),
    port: int = typer.Option(None, "--port"),
) -> None:
    """
    Run batch evaluation across multiple tasks and seeds.
    
    Orchestrates large-scale evaluations by running a policy on multiple
    tasks with multiple random seeds. Supports automatic task suite expansion,
    parallel execution, video recording, and multiple output formats.
    
    Results are saved in JSON format by default, with optional Markdown and
    CSV exports for analysis and reporting.
        
    :param policy_id: Identifier of the policy container to evaluate.
    :param env_id: Identifier of the environment container to use.
    :param backend: Name of the environment backend.
    :param tasks: Comma-separated task list or suite name.
    :param seeds: Comma-separated list of random seeds.
    :param max_steps: Maximum steps per episode.
    :param timeout: Timeout multiplier for each episode request.
    :param unnorm_key: Dataset key for action unnormalization.
    :param save_video: Whether to save videos of all episodes.
    :param video_dir: Directory for saving videos.
    :param output: Output directory for results files.
    :param format: Output format (json, markdown, csv, or all).
    :param parallel: Number of parallel evaluations to run.
    :param port: Daemon port number.
    """
    
    config = get_config()
    # Use config defaults
    port = port or config.daemon.port
    max_steps = max_steps if max_steps is not None else config.eval.max_steps
    timeout = timeout if timeout is not None else config.eval.timeout
    save_video = save_video if save_video is not None else config.eval.save_video
    video_dir = video_dir or config.eval.video_dir
    output_dir = Path(output).expanduser() if output else Path(config.eval.results_dir).expanduser()
    
    # Parse seeds
    seed_list = [int(s.strip()) for s in seeds.split(",")]
    
    # Parse tasks - check if it's a suite name or explicit task list
    task_list = []
    if "/" in tasks or "," in tasks:
        # Explicit task list
        task_list = [t.strip() for t in tasks.split(",")]
    else:
        # Suite name - fetch from daemon
        print(f"[cyan]Fetching tasks for suite '{tasks}'...[/cyan]")
        try:
            r = requests.get(f"{daemon_url(port)}/env/tasks/{backend}", params={"suite": tasks})

            if r.status_code == 200:
                suite_tasks = r.json().get(tasks, [])
                suite_tasks = [f'{tasks}/{s["index"]}' for s in suite_tasks]
                task_list = suite_tasks
                print(f"  Found {len(task_list)} tasks")
            else:
                # Fall back to treating it as a task prefix
                task_list = [tasks]
        except Exception as e:
            print(f"[yellow]Warning: Could not fetch suite tasks: {e}[/yellow]")
            task_list = [tasks]
    
    if not task_list:
        print("[red]Error: No tasks specified[/red]")
        raise typer.Exit(1)
    
    total_episodes = len(task_list) * len(seed_list)
    print(f"\n[bold cyan]Batch Evaluation[/bold cyan]")
    print(f"  Policy: {policy_id}")
    print(f"  Environment: {env_id}")
    print(f"  Tasks: {len(task_list)}")
    print(f"  Seeds: {seed_list}")
    print(f"  Total episodes: {total_episodes}")
    print(f"  Max steps: {max_steps}")
    if save_video:
        print(f"  Videos: {video_dir}")
    print()
    
    evaluator = BatchEvaluator(daemon_url=daemon_url(port))
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
        ) as progress:
            task = progress.add_task(f"Running {total_episodes} episodes...", total=total_episodes)
            
            results = evaluator.run(
                policy_id=policy_id,
                env_id=env_id,
                tasks=task_list,
                seeds=seed_list,
                max_steps=max_steps,
                timeout=timeout,
                unnorm_key=unnorm_key,
                save_video=save_video,
                video_dir=video_dir,
                parallel=parallel,
                progress_callback=lambda d, t, r: progress.update(task, completed=d),
            )
    except Exception as e:
        print(f"[red]Error during evaluation: {e}[/red]")
        raise typer.Exit(1)
    
    # Print summary
    print(f"\n{results.summary()}")
    
    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON (always save)
    json_path = output_dir / f"{results.batch_id}.json"
    results.save(json_path)
    
    # Additional formats
    if format == "markdown" or format == "all":
        md_path = output_dir / f"{results.batch_id}.md"
        md_path.write_text(format_results_markdown(results))
        print(f"[green]✓ Markdown saved:[/green] {md_path}")
    
    if format == "csv" or format == "all":
        csv_path = output_dir / f"{results.batch_id}.csv"
        csv_path.write_text(format_results_csv(results))
        print(f"[green]✓ CSV saved:[/green] {csv_path}")
    
    print(f"[green]✓ Results saved:[/green] {json_path}")

def main():
    """
    Entry point for the MAPLE CLI application.
    
    Invokes the Typer app to handle command-line argument parsing
    and command dispatch.
    """
    app()

if __name__ == "__main__":
    main()


