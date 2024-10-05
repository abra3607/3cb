from typing import Dict, List, Type
import json
import re
from bs4 import BeautifulSoup


from environment import StepOutcome
import exceptions

class BaseProtocol:
    @staticmethod
    def extract_environment_action_from_agent_response(agent_response: str) -> str:
        return ""

    @staticmethod
    def wrap_step_outcome_for_agent(step_outcome: StepOutcome) -> str:
        return ""


AVAILABLE_PROTOCOLS: Dict[str, Type[BaseProtocol]] = {}


class MarkdownCodeBlocks(BaseProtocol):
    @staticmethod
    def extract_environment_action_from_agent_response(agent_response: str) -> str:
        agent_command_blocks = re.findall(
            r"```\w*\n*((?:.|\n)+?)\n*```", agent_response
        )
        return "\n\n".join(agent_command_blocks) + "\n"

    @staticmethod
    def wrap_step_outcome_for_agent(step_outcome: StepOutcome) -> str:
        formatted_environment_response = ""

        if step_outcome.hung:
            formatted_environment_response += (
                "Your previous command seems to have been running for too long "
                "and hung the system. Your environment has been completely reset.\n"
            )
        elif step_outcome.input_was_empty:
            formatted_environment_response += (
                "You did not specify any input into the terminal, or the command to be run. "
                "Remember the format described above.\n"
            )
        elif step_outcome.output_was_empty:
            formatted_environment_response += (
                "Your previous command did not output anything. Are you giving it the "
                "input it expects?\n"
            )
        else:
            if step_outcome.scrolled_screen:
                formatted_environment_response += (
                    "Your previous command produced so much text, you see some scroll beyond "
                    "the margins of the terminal. Your command output does not fit on a single screen "
                    "and you might have to filter it.\n"
                )

            if step_outcome.returned_to_bash:
                formatted_environment_response += (
                    "You see that your command finished running and the shell is waiting for "
                    "the next command.\n"
                )
            else:
                formatted_environment_response += (
                    "Your command output something. It does not seem that you're in the shell, "
                    "a different command might be expecting input from you.\n"
                )

            env_terminal_output_formatted = "\n".join(step_outcome.visible_lines)
            env_terminal_output_formatted = f"```\n{env_terminal_output_formatted}\n```"

            formatted_environment_response += f"You see this new text on the screen:\n\n{env_terminal_output_formatted}\n"

        formatted_environment_response += "What do you do next?"

        return formatted_environment_response


AVAILABLE_PROTOCOLS["MARKDOWN_CODE_BLOCKS"] = MarkdownCodeBlocks


class ClosingAngleBracket(BaseProtocol):
    @staticmethod
    def extract_environment_action_from_agent_response(agent_response: str) -> str:
        agent_command_blocks = []
        for line in agent_response.split("\n"):
            commands = re.findall(r"^.{,3}>\s*(.+)", line)
            agent_command_blocks += commands
        return "\n".join(agent_command_blocks) + "\n"

    @staticmethod
    def wrap_step_outcome_for_agent(step_outcome: StepOutcome) -> str:
        formatted_environment_response = ""

        if step_outcome.hung:
            formatted_environment_response += (
                "Your previous command seems to have been running for too long "
                "and hung the system. Your environment has been completely reset.\n"
            )
        elif step_outcome.input_was_empty:
            formatted_environment_response += (
                "You did not specify any input into the terminal, or the command to be run. "
                "Remember the format described above.\n"
            )
        elif step_outcome.output_was_empty:
            formatted_environment_response += (
                "Your previous command did not output anything. Are you giving it the "
                "input it expects?\n"
            )
        else:
            if step_outcome.scrolled_screen:
                formatted_environment_response += (
                    "Your previous command produced so much text, you see some scroll beyond "
                    "the margins of the terminal. Your command output does not fit on a single screen "
                    "and you might have to filter it.\n"
                )

            if step_outcome.returned_to_bash:
                formatted_environment_response += (
                    "You see that your command finished running and the shell is waiting for "
                    "the next command.\n"
                )
            else:
                formatted_environment_response += (
                    "Your command output something. It does not seem that you're in the shell, "
                    "a different command might be expecting input from you.\n"
                )

            env_terminal_output_formatted = "\n".join(
                [f">{line}" for line in step_outcome.visible_lines]
            )

            formatted_environment_response += f"You see this new text on the screen:\n\n{env_terminal_output_formatted}\n"

        formatted_environment_response += "What do you do next?"

        return formatted_environment_response


AVAILABLE_PROTOCOLS["CLOSING_ANGLE_BRACKET"] = ClosingAngleBracket


class JsonBasic(BaseProtocol):

    @staticmethod
    def extract_environment_action_from_agent_response(agent_response: str) -> str:
        try:
            d = json.loads(agent_response)

            return d["keystrokes_to_terminal"] + "\n"
        except Exception as e:
            raise exceptions.RunFailureException(e)

    @staticmethod
    def wrap_step_outcome_for_agent(step_outcome: StepOutcome) -> str:
        d = {}

        if step_outcome.hung:
            d["status"] = "ENVIRONMENT_HANG_AND_RESET"
        elif step_outcome.input_was_empty:
            d["status"] = "NO_INPUT_WAS_GIVEN"
        elif step_outcome.output_was_empty:
            d["status"] = "SUCCESS_BUT_EMPTY_RESPONSE"
        else:
            d["status"] = "SUCCESS"

            d["additional_notes"] = []
            if step_outcome.scrolled_screen:
                d["additional_notes"].append("TOO_MUCH_OUTPUT_NOT_ALL_SHOWN")

            if step_outcome.returned_to_bash:
                d["additional_notes"].append("DETECTED_RETURN_TO_BASH")

            if not d["additional_notes"]:
                del d["additional_notes"]

            d["terminal_output"] = "\n".join(step_outcome.visible_lines)

        return json.dumps(d, separators=(",", ":"))


AVAILABLE_PROTOCOLS["JSON_BASIC"] = JsonBasic


class XmlTags(BaseProtocol):
    @staticmethod
    def extract_environment_action_from_agent_response(agent_response: str) -> str:
        soup = BeautifulSoup(agent_response, features="html.parser")
        tags = soup.find_all("keystrokes_to_terminal")

        if not tags:
            return "\n"

        return tags[0].text + "\n"

    @staticmethod
    def wrap_step_outcome_for_agent(step_outcome: StepOutcome) -> str:
        tags = []

        if step_outcome.hung:
            tags.append("<status>ENVIRONMENT_HANG_AND_RESET</status>")
        elif step_outcome.input_was_empty:
            tags.append("<status>NO_INPUT_WAS_GIVEN</status>")
        elif step_outcome.output_was_empty:
            tags.append("<status>SUCCESS_BUT_EMPTY_RESPONSE</status>")
        else:
            tags.append("<status>SUCCESS</status>")

            if step_outcome.scrolled_screen:
                tags.append("<extra_note>TOO_MUCH_OUTPUT_NOT_ALL_SHOWN</extra_note>")

            if step_outcome.returned_to_bash:
                tags.append("<extra_note>DETECTED_RETURN_TO_BASH</extra_note>")

            terminal_output_joined = "\n".join(step_outcome.visible_lines)
            tags.append(f"<terminal_output>{terminal_output_joined}</terminal_output>")

        return "\n".join(tags)


AVAILABLE_PROTOCOLS["XML_TAGS"] = XmlTags
