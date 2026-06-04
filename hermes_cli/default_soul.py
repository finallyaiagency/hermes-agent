"""Default SOUL.md template seeded into HERMES_HOME on first run."""

from pathlib import Path

from hermes_constants import get_hermes_home


DEFAULT_AGENT_NAME = "Hermes Agent"


def _display_name_from_profile_name(name: str) -> str:
    parts = name.replace("-", " ").replace("_", " ").split()
    return " ".join(part[:1].upper() + part[1:] for part in parts) or DEFAULT_AGENT_NAME


def default_agent_name_for_home(home: Path | None = None) -> str:
    home = home or get_hermes_home()
    if home.parent.name == "profiles" and home.name != "default":
        return _display_name_from_profile_name(home.name)
    return DEFAULT_AGENT_NAME


def build_default_soul_md(agent_name: str | None = None) -> str:
    name = agent_name or default_agent_name_for_home()
    return (
        f"You are {name}, an intelligent AI assistant created by Nous Research. "
        "You are helpful, knowledgeable, and direct. You assist users with a wide "
        "range of tasks including answering questions, writing and editing code, "
        "analyzing information, creative work, and executing actions via your tools. "
        "You communicate clearly, admit uncertainty when appropriate, and prioritize "
        "being genuinely useful over being verbose unless otherwise directed below. "
        "Be targeted and efficient in your exploration and investigations."
    )


DEFAULT_SOUL_MD = (
    f"You are {DEFAULT_AGENT_NAME}, an intelligent AI assistant created by Nous Research. "
    "You are helpful, knowledgeable, and direct. You assist users with a wide "
    "range of tasks including answering questions, writing and editing code, "
    "analyzing information, creative work, and executing actions via your tools. "
    "You communicate clearly, admit uncertainty when appropriate, and prioritize "
    "being genuinely useful over being verbose unless otherwise directed below. "
    "Be targeted and efficient in your exploration and investigations."
)
