#!/usr/bin/env python3
import fire
import os

from config_schema import TaskConfig
from environment import DockerEnvironment


def main(
    config_path: str,
):
    task_config = TaskConfig.from_config(config_path)

    env = DockerEnvironment(task_config.name, task_config.environments["main"])
    env.build()

    os.execvp("sh", ["sh", "-c", f"docker run -it {env.task_name_simplified}"])


if __name__ == "__main__":
    fire.Fire(main)
