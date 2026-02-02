import typer 
import requests
from rich import print
from pathlib import Path
from typing import Optional
from rich.progress import Progress, SpinnerColumn, TextColumn

from maple.cmd.cli.misc import daemon_url
from maple.config import config, load_config
from maple.cmd.cli import pull_app, serve_app, list_app, env_app, config_app
from maple.utils.logging import setup_logging, get_logger
from maple.eval import BatchEvaluator, format_results_markdown, format_results_csv

log = get_logger("cli")

app = typer.Typer(no_args_is_help= True)

@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[Path] = typer.Option(None, "--log-file", help="Write logs to file"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    load_config(config_file)
    
    # Override with CLI args
    level = "DEBUG" if verbose else config.logging.level
    log_path = log_file or (Path(config.logging.file) if config.logging.file else None)
    setup_logging(level=level, log_file=log_path, verbose=verbose)

app.add_typer(pull_app, name="pull", help="Download management of envs and policies")
app.add_typer(serve_app, name="serve", help="Spin docker containers")
app.add_typer(list_app, name="list")
app.add_typer(env_app, name="env")
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
):
    """
    Run a policy on an environment task.
    """

    port = port or config.daemon.port
    max_steps = max_steps if max_steps is not None else config.run.max_steps
    timeout = timeout if timeout is not None else config.run.timeout
    save_video = save_video if save_video is not None else config.run.save_video
    video_dir = video_dir or config.run.video_dir
    
    payload = {
        "policy_id": policy_id,
        "env_id": env_id,
        "task": task,
        "max_steps": max_steps,
        "save_video": save_video,
    }
    
    if instruction:
        payload["instruction"] = instruction
    if seed is not None:
        payload["seed"] = seed
    if unnorm_key:
        payload["unnorm_key"] = unnorm_key
    if video_dir:
        payload["video_dir"] = video_dir
    
    try:
        with Progress(SpinnerColumn(),TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task(f"Running policy on task...")
            print(f"  Policy: {policy_id}")
            print(f"  Env: {env_id}")
            print(f"  Task: {task}")
            print(f"  Max steps: {max_steps}")
            r = requests.post(
                f"{daemon_url(port)}/run",
                json=payload,
                timeout=int(max_steps * timeout),  # Generous timeout
            )
    except requests.exceptions.Timeout:
        print(f"[red]Error:[/red] Request timed out after {max_steps * timeout}s")
        raise typer.Exit(1)

    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)

    result = r.json()
    
    # Display results
    success = result.get("success", False)
    if success:
        print(f"\n[bold green]✓ Task completed successfully![/bold green]")
    else:
        print(f"\n[yellow]Task finished (not successful)[/yellow]")
    
    print(f"\n[cyan]Results:[/cyan]")
    print(f"  Run ID: {result.get('run_id')}")
    print(f"  Steps: {result.get('steps')}")
    print(f"  Total Reward: {result.get('total_reward', 0):.4f}")
    print(f"  Terminated: {result.get('terminated')}")
    print(f"  Truncated: {result.get('truncated')}")
    
    if result.get("video_path"):
        print(f"  Video saved: {result.get('video_path')}")

@app.command("status")
def status(port: int = typer.Option(None, "--port")):

    port = port or config.daemon.port
    try:
        r = requests.get(f"http://0.0.0.0:{port}/status", timeout=1)
        data = r.json()
        print("[bold green]MAPLE daemon running[/bold green]")
        print(data)
    except requests.exceptions.ConnectionError:
        print("[red]MAPLE daemon not running[/red]")

@app.command("stop")
def stop(port: int = typer.Option(None, "--port")):
    
    port = port or config.daemon.port
    try:
        requests.post(f"{daemon_url(port)}/stop")
        print("[green]MAPLE daemon stopped[/green]")
    except requests.exceptions.ConnectionError:
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
):
    """
    Run batch evaluation across multiple tasks and seeds.
    
    Examples:
        # Evaluate on specific tasks
        vla eval openvla-7b-abc libero-xyz --tasks libero_10/0,libero_10/1 --seeds 0,1,2
        
        # Evaluate on a suite (fetches tasks from env)
        vla eval openvla-7b-abc libero-xyz --tasks libero_10 --seeds 0,1,2
        
        # Save results and videos
        vla eval openvla-7b-abc libero-xyz --tasks libero_10 --output results/ --save-video
    """
    
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
    app()

if __name__ == "__main__":
    main()


