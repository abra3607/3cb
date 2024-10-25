<div align="center">
  <h1>🌋 Catastrophic Cyber Capabilities Benchmark (3CB)</h1>
  <p>AI is improving rapidly and rogue or misapplied AI presents large-scale, novel risks to society. The clearest failure cases involve cyber capabilities. With this project, we aim to provide a robust measure of how developed the cyber capabilities of contemporary models are.</p>
</div>

- [The project page](https://www.notion.so/apartresearch/cyber-evals-129a3c19ff814b4eab974186ac5cfd38?pvs=4)
- [The paper](https://arxiv.org/abs/2410.09114)
- [The slide deck](https://abra.me/3cb)
- [The talk](https://www.youtube.com/watch?v=ydiV10RGWY4)
- [The older talk](https://www.youtube.com/watch?v=4vQ8D4A3KNg)

## How to set up the environment

1. Check out the repo with `git clone` in your desired folder.

1. Your host must have the docker service running and docker-cli available. The CE / os packaged version is also fine.
    
    1. E.g. on Debian follow these steps: https://docs.docker.com/engine/install/debian/

1. Copy `.env.template` to `.env` and customize it, setting the name of the local sqlite instance and your API keys.

1. Run `poetry install` to get the necessary Python packages

1. Run `poetry run alembic upgrade head` to set up the local database

1. Try executing a run with

    ```bash
    poetry run python3 run_from_config.py \
      --config_path ./task_configs/binpwn_gdb_repl.toml \
      --elicitation_index 1 \
      --agent_identifier openai \
      --model_name gpt-4o-2024-08-06 \
      --print_comms true
    ```

## Broad architecture overview

* `model.py` holds ORM definitions for the local sqlite database, to which everything is persisted.
* `config_schema.py` contains the Pydantic schemas for Task configuration objects and everything they need.
* `task_configs/` contains the task configurations themselves, which conform to the config schema.
* `alembic*` holds data for management of the local DB, such as the version upgrade files.
* `protocol.py` has the definitions for different ways of extracting the agent action from the model output, and wrapping env output for the agent.
* `exceptions.py` define different ways things can go wrong during a run.
* `environment.py` hold code to manage Docker images and containers which implement the sandboxes.
* `agent.py` defines basic agent setups from common API providers.
* `harness.py` brings everything together and implements actually running an agent in an environment against a task.

### Useful scripts

* `run_from_config.py --config_path <config>.toml` allows you to create a run from a given task_config.
* `debug_task_env.py --config_path <config>.toml` allows you to build a Docker image defined by a task_config and get a shell there.

## How to contribute

### Create a new task

1. Find a good task idea, you're welcome to be inspired by existing CTF Jeopardy tasks, by real-world eng tasks, etc etc.
1. Create a new toml file in `task_configs/`.
1. Define the environment, pay special attention to the Dockerfile and the packaged bash scripts.
1. Make sure you yourself can finish the task when run with `debug_task_env.py`.
1. Create an elicitation or two, you probably want to use XML_TAGS as the protocol first.
1. Send a PR.

### Create a new elicitation for an existing task

1. Find a task and run it a bunch of times locally.
1. Identify where you think the model is hampered by insufficient understanding of its environment, the problem as posed, communication protocol, etc. Or where a $200 tip can help.
1. Add another `[[elicitations]]` entry to the relevant toml config.
1. As long as there's a combination of (task, model), where the model performs better than status quo, it's valuable.
1. Send a PR.

### More interesting contributions?

1. Chat with me on discord: abra3607

### Challenge guidelines

- Not very many steps (~GPT-4 should be able to have successful runs in ~20 steps)
- Don't go overboard on hinting in the prompt (a general agent should be able to go through the challenge in theory)
- Don't over-engineer what the challenge looks like (as long as it models some cyber capability and the model succeeds, it's fine)
