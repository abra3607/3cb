#!/usr/bin/env python3
import numpy as np
import asyncio
import multiprocessing
from collections import Counter
import fire
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from harness import Harness
from agent import AGENT_FROM_IDENTIFIER, BaseAgent
from config_schema import TaskConfig

harness = Harness()


async def single_run_from_config(
    task_config: TaskConfig, elicitation_index: int, agent: BaseAgent, print_comms: bool
):
    run = await harness.run(
        task_config=task_config,
        elicitation_index=elicitation_index,
        agent=agent,
        print_comms=print_comms,
    )
    return run.status


def sync_wrapper_for_multiprocessing(args):
    return asyncio.run(single_run_from_config(*args))


def main(
    config_path: str,
    elicitation_index: int,
    agent_identifier: str = "anthropic",
    model_name: str = "claude-3-5-sonnet-20241022",
    total_runs: int = 1,
    parallel_runs: int = 1,
    print_comms: bool = True,
):
    agent_class = AGENT_FROM_IDENTIFIER[agent_identifier]
    agent = agent_class(model_name=model_name)

    task_config = TaskConfig.from_config(config_path)
    args = [(task_config, elicitation_index, agent, print_comms)]
    args *= total_runs
    np.random.shuffle(args)

    console = Console()

    statuses = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        expand=True,
    ) as progress:
        overall_task = progress.add_task("[cyan]Overall Progress", total=len(args))
        run_tasks = [
            progress.add_task(f"[green]Run {i+1}", total=1) for i in range(len(args))
        ]

        with multiprocessing.Pool(processes=parallel_runs) as pool:
            for i, status in enumerate(
                pool.imap_unordered(sync_wrapper_for_multiprocessing, args)
            ):
                progress.update(
                    run_tasks[i], advance=1, description=f"[green]Run {i+1}: {status}"
                )
                progress.update(overall_task, advance=1)
                statuses.append(status)

    status_counts = Counter(statuses)
    total_runs = len(statuses)

    table = Table(title="Run Status Summary")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Percentage", style="green")

    for status, count in status_counts.items():
        percentage = (count / total_runs) * 100
        table.add_row(str(status), str(count), f"{percentage:.2f}%")

    console.print(Panel(table, title="Summary", expand=False))


if __name__ == "__main__":
    fire.Fire(main)
