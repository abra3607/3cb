from transformers import AutoTokenizer
import time
from typing import List
import openai
import anthropic
import replicate
import os

import model
import exceptions


class BaseAgent:
    def __init__(self):
        pass

    def reset(self):
        pass

    def premember(self, messages: List[model.ChatMessage]):
        pass

    def act(self, environment_response: str) -> str:
        return ""

    def get_identifier(self) -> str:
        return f"{IDENTIFIER_FROM_AGENT[self.__class__]}"


class OpenAiApiAgent(BaseAgent):
    openai_client = openai.OpenAI(
        # api key comes from the env variable
    )

    def __init__(self, model_name):
        # eg gpt-4-turbo-preview
        self.model_name = model_name

    def reset(self):
        self.messages = []

    def premember(self, messages: List[model.ChatMessage]):
        self.messages += [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

    def act(self, environment_response: str) -> str:
        self.messages.append(
            {
                "role": "user",
                "content": environment_response,
            }
        )

        try:
            chat_completion = self.openai_client.chat.completions.create(
                messages=self.messages,
                # temperature=0.9,
                model=self.model_name,
                extra_body=dict(
                    max_completion_tokens=1024,
                ),
            )
        except openai.BadRequestError as e:
            if e.code == 'invalid_prompt':
                raise exceptions.RunRefusedException()
            raise e

        content = str(chat_completion.choices[0].message.content)

        if not content:
            raise exceptions.RunRefusedException()

        self.messages.append(
            {
                "role": chat_completion.choices[0].message.role,
                "content": content,
            }
        )

        return content

    def get_identifier(self) -> str:
        return f"{IDENTIFIER_FROM_AGENT[self.__class__]}/{self.model_name}"


class TogetherApiAgent(BaseAgent):
    together_client = openai.OpenAI(
        base_url="https://api.together.xyz",
        api_key=os.getenv("TOGETHER_API_KEY"),
    )

    def __init__(self, model_name):
        # eg Qwen/Qwen1.5-72B-Chat
        self.model_name = model_name

    def reset(self):
        self.messages = []

    def premember(self, messages: List[model.ChatMessage]):
        self.messages += [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

    def act(self, environment_response: str) -> str:
        self.messages.append(
            {
                "role": "user",
                "content": environment_response,
            }
        )

        retries = 0
        while True:
            try:
                chat_completion = self.together_client.chat.completions.create(
                    messages=self.messages,
                    model=self.model_name,
                    max_tokens=1024,
                )
                break
            except (openai.APITimeoutError, openai.RateLimitError) as e:
                time.sleep(40)
                retries += 1
                if retries == 30:
                    print("Retried 30 times, giving up")
                    raise e
            except openai.BadRequestError as e:
                if 'Input validation error: `inputs` tokens + `max_new_tokens` must be <=' in e.message:
                    raise exceptions.RunFailureException("Hit the token limit")
                raise e

        self.messages.append(
            {
                "role": chat_completion.choices[0].message.role,
                "content": chat_completion.choices[0].message.content,
            }
        )

        return str(chat_completion.choices[0].message.content)

    def get_identifier(self) -> str:
        return f"{IDENTIFIER_FROM_AGENT[self.__class__]}/{self.model_name}"


class ReplicateApiAgent(BaseAgent):
    def __init__(self, model_name):
        # api key comes from the env variable
        self.model_name = model_name

    def reset(self):
        self.messages = []

    def premember(self, messages: List[model.ChatMessage]):
        self.messages += messages

    def act(self, environment_response: str) -> str:
        self.messages.append(
            {
                "role": "user",
                "content": environment_response,
            }
        )

        # weirdly they're named differently on replicate and huggingface
        replicate_to_hf_model_names = {
            "meta/meta-llama-3-8b-instruct": "meta-llama/Meta-Llama-3-8B-Instruct",
            "meta/meta-llama-3-70b-instruct": "meta-llama/Meta-Llama-3-70B-Instruct",
            "meta/meta-llama-3.1-405b-instruct": "meta-llama/Meta-Llama-3.1-405B-Instruct",
            "mistralai/mixtral-8x7b-instruct-v0.1": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        }

        hf_model_name = replicate_to_hf_model_names[self.model_name]

        def format(messages, hf_model_name):
            tokenizer = AutoTokenizer.from_pretrained(hf_model_name)
            return tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

        response_stream = replicate.run(
            self.model_name,
            input={
                "prompt": format(self.messages, hf_model_name),
                "max_tokens": 1024,
                "system_prompt": "You are a helpful assistant.",
            },
        )
        response = "".join(str(res) for res in response_stream)

        self.messages.append(dict(role="assistant", content=response))

        return response

    def get_identifier(self) -> str:
        return f"{IDENTIFIER_FROM_AGENT[self.__class__]}/{self.model_name}"


class AnthropicAgent(BaseAgent):
    client = anthropic.Anthropic(
        # api key comes from the env variable
    )

    def __init__(self, model_name):
        # eg claude-3-opus-20240229
        self.model_name = model_name

    def reset(self):
        self.messages = []

    def premember(self, messages: List[model.ChatMessage]):
        self.messages += [
            {
                "role": message.role,
                "content": [{"type": "text", "text": message.content}],
            }
            for message in messages
        ]

    def act(self, environment_response: str) -> str:
        self.messages.append(
            {
                "role": "user",
                "content": [{"type": "text", "text": environment_response}],
            }
        )
        self.messages[-1]['content'][0].update({
            "cache_control": {"type": "ephemeral"},
        })

        while True:
            try:
                generated_message = self.client.messages.create(
                    messages=self.messages,
                    model=self.model_name,
                    max_tokens=1024,
                    extra_headers={
                        'anthropic-beta': 'prompt-caching-2024-07-31',
                    }
                )
                del self.messages[-1]['content'][0]["cache_control"]
            except Exception as e:
                if getattr(e, "status_code") in [429, 529, 500]:
                    time.sleep(1)
                    continue
                else:
                    raise e
            break

        self.messages.append(
            {
                "role": generated_message.role,
                "content": generated_message.content[0].text,
            }
        )

        return str(generated_message.content[0].text)

    def get_identifier(self) -> str:
        return f"{IDENTIFIER_FROM_AGENT[self.__class__]}/{self.model_name}"


class HumanAgent(BaseAgent):
    def __init__(self):
        pass

    def reset(self):
        pass

    def premember(self, messages):
        pass

    def act(self, environment_response: str) -> str:
        time.sleep(0.1)
        return input()


AGENT_FROM_IDENTIFIER = dict(
    openai=OpenAiApiAgent,
    together=TogetherApiAgent,
    anthropic=AnthropicAgent,
    human=HumanAgent,
    replicate=ReplicateApiAgent,
)

IDENTIFIER_FROM_AGENT = {j: i for i, j in AGENT_FROM_IDENTIFIER.items()}
