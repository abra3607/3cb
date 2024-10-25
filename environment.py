from dataclasses import dataclass
import numpy as np
import time
import os
import multiprocessing
from typing import List, cast
import random
import string
import re
import docker
from docker.models.containers import Container
import pyte
import base64
import toml

import exceptions
from config_schema import EnvironmentConfig


amap = lambda *args, **kwargs: np.array(list(map(*args)), **kwargs)

debug_docker = False


@dataclass(frozen=True)
class StepOutcome:
    hung: bool
    scrolled_screen: bool
    returned_to_bash: bool
    input_was_empty: bool
    output_was_empty: bool
    all_output: bytes
    visible_lines: List[str]


class DockerEnvironment:
    docker_client = docker.from_env()

    def __init__(self, task_name: str, environment_config: EnvironmentConfig):
        self.task_name = task_name
        self.task_name_simplified = re.sub(r"\W", "", self.task_name).lower()
        self.environment_config = environment_config
        self.docker_config = environment_config.docker
        self.container_name = (
            f"challenge_sandbox_from_pid{multiprocessing.current_process().pid}"
        )

    def generate_random_string(self, length=8):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def stop(self):
        try:
            container = cast(
                Container, self.docker_client.containers.get(self.container_name)
            )
            container.stop(timeout=1)
            container.wait(timeout=10, condition="removed")
        except docker.errors.NotFound:
            pass

    def build(self):
        try:
            build_fingerprint = hash(toml.dumps(self.environment_config.model_dump()))

            build_context_path = os.path.join(
                "/tmp",
                f"docker_build_{build_fingerprint}",
            )
            os.makedirs(build_context_path, exist_ok=True)

            for filename, content in self.environment_config.files.items():
                with open(os.path.join(build_context_path, filename), "w") as file:
                    file.write(content)

            for filename, content in self.environment_config.files_b64.items():
                with open(os.path.join(build_context_path, filename), "wb") as file:
                    file.write(base64.b64decode(content))

            build_output = self.docker_client.images.build(
                path=build_context_path,
                tag=self.task_name_simplified,
                rm=True,
                forcerm=True,
            )
            if debug_docker:
                print(f"Building Docker image: {self.task_name_simplified}")
                for line in build_output[1]:
                    if "stream" in line:
                        print(line["stream"].strip())
                    elif "error" in line:
                        print(f"Error: {line['error'].strip()}")
                    elif "message" in line:
                        print(f"Message: {line['message'].strip()}")

        except docker.errors.BuildError as e:
            if debug_docker:
                print(f"Build failed: {str(e)}")
                for log in e.build_log:
                    if "stream" in log:
                        print(log["stream"].strip())
                    elif "error" in log:
                        print(f"Error: {log['error'].strip()}")
            raise e

    def reset(self):
        self.build()

        with open(
            "./docker_seccomp_profile_allowing_ADDR_NO_RANDOMIZE.json"
        ) as file:
            seccomp_profile = file.read()

        self.stop()

        self.container = cast(
            Container,
            self.docker_client.containers.run(
                image=f"{self.task_name_simplified}:latest",
                name=self.container_name,
                hostname=self.docker_config.hostname,
                detach=True,
                tty=True,
                stdin_open=True,
                stdout=True,
                stderr=True,
                auto_remove=True,
                cap_add=self.docker_config.cap_add,
                security_opt=[
                    # TODO: make work with setuid, specify in dockerconfig?
                    # "no-new-privileges",
                    f"seccomp={seccomp_profile}",
                ],
                cpu_period=self.docker_config.cpu_period,
                cpu_quota=self.docker_config.cpu_quota,
                mem_limit=self.docker_config.mem_limit,
            ),
        )

        self.socket = self.container.attach_socket(
            params=dict(
                stdin=True,
                stdout=True,
                stderr=True,
                stream=True,
            )
        )

        self.socket._sock.setblocking(0)
        self.socket._writing = True

        self.emulated_terminal = pyte.HistoryScreen(80, 24)
        self.emulated_terminal_stream = pyte.ByteStream(self.emulated_terminal)

    def get_container_cpu_usage(self):
        d = self.container.stats(stream=False)
        cpu_usage_delta = (
            d["cpu_stats"]["cpu_usage"]["total_usage"]
            - d["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_usage_delta = (
            d["cpu_stats"]["system_cpu_usage"] - d["precpu_stats"]["system_cpu_usage"]
        )
        return cpu_usage_delta * d["cpu_stats"]["online_cpus"] / system_usage_delta

    def act(self, terminal_input_bytes: bytes) -> StepOutcome:
        if not terminal_input_bytes:
            return StepOutcome(
                hung=False,
                scrolled_screen=False,
                returned_to_bash=False,
                input_was_empty=True,
                output_was_empty=True,
                all_output=b"",
                visible_lines=[],
            )

        self.socket.write(terminal_input_bytes)
        
        time.sleep(0.2)

        try:
            self.docker_client.containers.get(self.container_name)
        except docker.errors.NotFound as e:
            raise exceptions.RunFailureException(e)

        time.sleep(0.8)

        if self.get_container_cpu_usage() > 0.2:
            time.sleep(10)

        container_response = b""
        while b := self.socket.read(1024):
            container_response += b

        if not container_response:
            return StepOutcome(
                hung=False,
                scrolled_screen=False,
                returned_to_bash=False,
                input_was_empty=False,
                output_was_empty=True,
                all_output=container_response,
                visible_lines=[],
            )

        self.emulated_terminal.reset()
        self.emulated_terminal_stream.feed(container_response)

        scrolled_screen = len(self.emulated_terminal.history.top) > 0

        stripped_lines = amap(str.strip, self.emulated_terminal.display)
        nonempty_idx = np.where(stripped_lines != "")[0]
        if len(nonempty_idx) == 0:
            return StepOutcome(
                hung=False,
                scrolled_screen=scrolled_screen,
                returned_to_bash=False,
                input_was_empty=False,
                output_was_empty=True,
                all_output=container_response,
                visible_lines=[],
            )

        last_nonempty_index = nonempty_idx[-1]
        visible_lines = self.emulated_terminal.display[: last_nonempty_index + 1]

        visible_lines = [line.rstrip() for line in visible_lines]

        returned_to_bash = "root@simurgh:" in visible_lines[-1]

        return StepOutcome(
            hung=False,
            scrolled_screen=scrolled_screen,
            returned_to_bash=returned_to_bash,
            input_was_empty=False,
            output_was_empty=False,
            all_output=container_response,
            visible_lines=visible_lines,
        )
