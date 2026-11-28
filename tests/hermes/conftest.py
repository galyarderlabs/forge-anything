from pathlib import Path

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx._hooks = {}
    ctx._skills = {}
    ctx._descriptions = {}
    ctx._commands = {}
    ctx._injected = []

    def register_hook(event, fn):
        ctx._hooks[event] = fn

    def register_skill(name, path, description="", frontmatter=None):
        # Mimic hermes' real register_skill, which calls path.exists() and
        # therefore breaks on a str (the bug that silently disabled the whole
        # plugin, found 2026-07-23). Keeping that fidelity here means a
        # regression to str paths fails these tests instead of failing
        # silently inside hermes.
        if not isinstance(path, Path):
            raise AttributeError(
                f"register_skill requires a pathlib.Path, got {type(path).__name__}"
            )
        ctx._skills[name] = path
        ctx._descriptions[name] = description

    def register_command(name, handler, description=""):
        ctx._commands[name] = (handler, description)

    def inject_message(content, role="user", session_key=None, origin=None):
        ctx._injected.append(
            {"content": content, "role": role, "session_key": session_key}
        )
        return True

    ctx.register_hook.side_effect = register_hook
    ctx.register_skill.side_effect = register_skill
    ctx.register_command.side_effect = register_command
    ctx.inject_message.side_effect = inject_message
    return ctx
