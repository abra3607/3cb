from pydantic import BaseModel, Field, field_validator
from typing import List, Dict
import toml


class DockerConfig(BaseModel):
    hostname: str = "simurgh"
    cpu_period: int = 100000
    cpu_quota: int = 200000
    mem_limit: str = "8g"
    cap_add: List[str] = ["NET_RAW"]

    @classmethod
    def make_default(cls):
        return DockerConfig()


class PrefilledMessage(BaseModel):
    role: str
    content: str

    @field_validator("content")
    @classmethod
    def strip_whitespace(cls, content):
        return content.strip()


class Elicitation(BaseModel):
    terminal_interop_protocol: str
    prefilled_messages: List[PrefilledMessage]

    @classmethod
    def from_toml(cls, toml_content: str):
        return cls.model_validate(toml.loads(toml_content))

    def to_normalized_toml(self) -> str:
        python_dict = self.model_dump(
            by_alias=True,
            exclude_none=True,
            include={"terminal_interop_protocol", "prefilled_messages"},
        )
        return toml.dumps(python_dict)


class EnvironmentConfig(BaseModel):
    docker: DockerConfig = Field(default_factory=DockerConfig.make_default)
    files: Dict[str, str]
    files_b64: Dict[str, str] = Field(default_factory=dict)


class RulesetConfig(BaseModel):
    max_turns: int
    flag: str


class TaskConfig(BaseModel):
    # increment when adding breaking changes, or implement conversion
    name: str
    version: str = Field(pattern=r"0\.3")
    tags: Dict[str, str] = Field(default_factory=dict)
    ruleset: RulesetConfig
    environments: Dict[str, EnvironmentConfig]
    elicitations: List[Elicitation]

    @classmethod
    def from_toml(cls, toml_content: str):
        return cls.model_validate(toml.loads(toml_content))

    @classmethod
    def from_config(cls, config_path: str) -> 'TaskConfig':
        with open(config_path, "r") as f:
            return TaskConfig.from_toml(f.read())

    def to_toml(self) -> str:
        python_dict = self.model_dump(by_alias=True, exclude_none=True)
        return toml.dumps(python_dict)

    def to_normalized_toml(self) -> str:
        python_dict = self.model_dump(
            by_alias=True,
            exclude_none=True,
            include={"version", "ruleset", "environments"},
        )
        return toml.dumps(python_dict)

