from typing import List
import docker
import replicate
import traceback
import sys

from config_schema import TaskConfig
from agent import BaseAgent
from environment import DockerEnvironment, StepOutcome
from protocol import AVAILABLE_PROTOCOLS
import model
import exceptions


class Harness:
    def __init__(self):
        pass

    async def run(
        self,
        task_config: TaskConfig,
        elicitation_index: int,
        agent: BaseAgent,
        print_comms=True,
    ) -> model.EvalRun:
        self.agent = agent
        self.agent.reset()

        self.messages: List[model.ChatMessage] = []

        async with model.database.transaction():
            task_config_snapshot, _ = await model.TaskConfigSnapshot.objects.get_or_create(
                name=task_config.name,
                toml_content=task_config.to_normalized_toml(),
            )
        elicitation = task_config.elicitations[elicitation_index]
        
        async with model.database.transaction():
            elicitation_snapshot, _ = await model.ElicitationSnapshot.objects.get_or_create(
                toml_content=elicitation.to_normalized_toml(),
            )

        run = await model.EvalRun(
            task_config_snapshot=task_config_snapshot,
            elicitation_snapshot=elicitation_snapshot,
            model=agent.get_identifier(),
            status="RUNNING",
        ).save()

        protocol = AVAILABLE_PROTOCOLS[elicitation.terminal_interop_protocol]

        for message in elicitation.prefilled_messages:
            message = await model.ChatMessage(
                run=run,
                ordinal=len(self.messages),
                role=message.role,
                content=message.content,
                is_prefilled=True,
            ).save()
            self.messages.append(message)

        agents_premember_was_called = False

        try:
            self.environment = DockerEnvironment(
                task_config.name, task_config.environments["main"]
            )
            try:
                self.environment.reset()
            except docker.errors.NotFound as e:
                # retriable
                raise exceptions.RunErrorException(e)

            for step_index in range(task_config.ruleset.max_turns):
                if self.messages[-1].role == "assistant":
                    # last message is already a prefilled LLM reply, we need to pass it in
                    # without actually calling the agent
                    # TODO: don't count as a turn
                    agent_response_full_text = self.messages[-1].content
                    underlying_communication = (
                        protocol.extract_environment_action_from_agent_response(
                            agent_response_full_text
                        )
                    )
                    if print_comms:
                        print(
                            f"\n### Last LLM gaslit reply:\n{agent_response_full_text}"
                        )
                else:
                    if not agents_premember_was_called:
                        if len(self.messages) > 1:
                            self.agent.premember(self.messages[:-1])
                        agents_premember_was_called = True

                    if self.agent.get_identifier() == "web":
                        agent_response_full_text = await self.agent.act(
                            self.messages[-1].content
                        )
                    else:
                        try:
                            agent_response_full_text = self.agent.act(
                                self.messages[-1].content
                            )
                        except replicate.exceptions.ModelError as e:
                            # todo: push this doing into the agent
                            raise exceptions.RunFailureException(e)

                    message = await model.ChatMessage(
                        run=run,
                        ordinal=len(self.messages),
                        role="assistant",
                        content=agent_response_full_text,
                        is_prefilled=False,
                        underlying_communication='<not extracted yet>',
                    ).save()
                    self.messages.append(message)

                    underlying_communication = (
                        protocol.extract_environment_action_from_agent_response(
                            agent_response_full_text
                        )
                    )
                    message.underlying_communication = underlying_communication
                    await message.update()

                    if print_comms:
                        print(f"\n### LLM replied:\n{agent_response_full_text}")

                if task_config.ruleset.flag in agent_response_full_text:
                    if print_comms:
                        print("\n### Win from the agent")
                    if agent.get_identifier() == "web":
                        await self.agent.win()

                    run.status = "SUCCESS"
                    await run.update()
                    return run

                environment_action = underlying_communication

                if environment_action:
                    try:
                        step_outcome = self.environment.act(environment_action.encode())
                    except docker.errors.NotFound as e:
                        raise exceptions.RunFailureException(e)
                else:
                    step_outcome = StepOutcome(
                        hung=False,
                        scrolled_screen=False,
                        returned_to_bash=False,
                        input_was_empty=True,
                        output_was_empty=True,
                        all_output=b"",
                        visible_lines=[],
                    )
                env_terminal_output = "\n".join(step_outcome.visible_lines)

                if step_outcome.hung:
                    if print_comms:
                        print("\n### Env was detected as hung and reset")
                    try:
                        self.environment.reset()
                    except docker.errors.NotFound as e:
                        # retriable
                        raise exceptions.RunErrorException(e)

                if task_config.ruleset.flag.encode() in step_outcome.all_output:
                    if print_comms:
                        print("\n### Win from the environment")
                    # save a fake-ish message for posterity
                    message = await model.ChatMessage(
                        run=run,
                        ordinal=len(self.messages),
                        role="user",
                        content=step_outcome.all_output.decode(),
                        is_prefilled=False,
                        underlying_communication=env_terminal_output,
                    ).save()
                    self.messages.append(message)

                    run.status = "SUCCESS"
                    await run.update()
                    return run

                environment_response = protocol.wrap_step_outcome_for_agent(
                    step_outcome
                )

                if print_comms:
                    print(
                        f"\n### Formatted reply from the container:\n{environment_response}"
                    )

                message = await model.ChatMessage(
                    run=run,
                    ordinal=len(self.messages),
                    role="user",
                    content=environment_response,
                    is_prefilled=False,
                    underlying_communication=env_terminal_output,
                ).save()
                self.messages.append(message)
            else:
                if print_comms:
                    print("\n### Ran out of turns, defaulting to failure")
                run.status = "FAILURE"
                await run.update()
                return run
        except exceptions.RunFailureException as e:
            print("\n### Non-retriable exception", e)
            exception_info = Harness._format_exception(e)
            print(exception_info)
            run.exception_stacktrace = exception_info

            run.status = "FAILURE"
            await run.update()
            return run
        except exceptions.RunRefusedException as e:
            print("\n### API refusal", e)
            exception_info = Harness._format_exception(e)
            print(exception_info)
            run.exception_stacktrace = exception_info

            run.status = "REFUSED"
            await run.update()
            return run
        except (exceptions.RunErrorException, Exception) as e:
            print("\n### Retriable exception", e)
            exception_info = Harness._format_exception(e)
            print(exception_info)
            run.exception_stacktrace = exception_info

            run.status = "ERROR"
            await run.update()
            return run
        finally:
            if self.environment:
                self.environment.stop()

    @staticmethod
    def _format_exception(e: Exception) -> str:
        # Capture the current exception information
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        # Format the traceback into a string
        traceback_string = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Get additional information
        error_message = str(e)
        error_type = type(e).__name__
        
        # Combine all information into a single string
        return f"""
        Error Type: {error_type}
        Error Message: {error_message}
        
        Full Traceback:
        {traceback_string}
        """
