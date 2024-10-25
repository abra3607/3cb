<div align="center">
  <h1>Agent Evals Workshop</h1>
</div>

- [Main doc](./README.md)

## How to get started

1. Get a linux box. Use your own or rent a cheap VPS e.g. from https://digitalocean.com (or Hetzner or AWS or whatever).

    1. (Example for digitalocean) Sign-up.
    1. Create a "droplet" ([tutorial here](https://docs.digitalocean.com/products/droplets/how-to/create/))
    1. Tier / size doesn't really matter, choose e.g. Ubuntu 24.04 LTS, add your ssh key.
    1. Connect with your ssh client ([another tutorial](https://docs.digitalocean.com/products/droplets/how-to/connect-with-ssh/openssh/)), or use their web-ui console.

1. Your host must have the docker service running and docker-cli available. The CE / os packaged version is also fine.
    
    1. Run this ([tutorial](https://docs.docker.com/engine/install/ubuntu/))

    ```bash
    # Add Docker's official GPG key:
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update

    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

1. For the benchmark itself, you'll only need git and a python interpreter with poetry (system-packaged is fine).

    ```bash
    apt install -y git python3-poetry
    ```

1. Check out the repo

    ```bash
    git clone https://github.com/apartresearch/3cb
    cd 3cb
    ```

1. Copy `.env.template` to `.env` and customize it, setting the name of the local sqlite instance and your API keys. For the bare minimum you'll only need your Anthropic API key.

    ```bash
    cp .env.template .env
    vim .env
    ```

1. Get the necessary Python packages

    ```bash
    poetry install
    ```

1. Set up the local database

    ```bash
    poetry run alembic upgrade head
    ```

1. Execute a run with this. It might take a minute to build the image.

    ```bash
    poetry run python3 run_from_config.py \
      --config_path ./task_configs/binpwn_gdb_repl.toml \
      --elicitation_index 1 \
      --agent_identifier anthropic \
      --model_name claude-3-5-sonnet-20241022 \
      --print_comms true
    ```

1. 🎉🎉🎉

## Things to try

- Load jupyter lab and tinker around with the repo code

    ```
    poetry add jupyterlab
    poetry run jupyter lab --allow-root --ip=$(hostname -I | awk '{print $1}')
    ```

- Run VSCode server on the VPS and connect to it

- Run tasks in parallel in bulk

- Analyze your results

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

* `poetry run python3 run_from_config.py --config_path <config>.toml` allows you to create a run from a given task_config.
* `poetry run python3 debug_task_env.py --config_path <config>.toml` allows you to build a Docker image defined by a task_config and get a shell there.

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

- Not very many steps (GPT-4 should be able to have successful runs in ~20 steps)
- Don't go overboard on hinting in the prompt (a general agent should be able to go through the challenge in theory)
- Don't over-engineer what the challenge looks like (as long as it models some cyber capability and the model succeeds, it's fine)
