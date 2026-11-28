#!/usr/bin/env python3
"""Render Forge Anything commands for every harness from commands/*.md.

Usage:
  python3 scripts/sync-commands.py          # rewrite the rendered outputs
  python3 scripts/sync-commands.py --check  # exit 1 on drift, change nothing

The source is commands/*.md, the Claude Code slash-command format. Every
other harness gets its own native render from that one source:

  commands/<name>.toml          Antigravity CLI (.toml, description + prompt)
  commands/rendered.json        Pi, Hermes, Copilot CLI (read at runtime)
  .opencode/commands/<name>.md  OpenCode (.md, description frontmatter)
  .cursor/commands/<name>.md    Cursor (.md, plain prompt)

Claude Code reads commands/*.md directly through .claude-plugin/plugin.json,
so it needs no render. Codex has no slash-command system (custom prompts are
deprecated and local-only), so it reaches commands through the MCP
(read_command) and the skills; nothing is rendered for it.

The render rewrites one line: the trailing **Note** that names a
`forge-anything:` agent or skill. Other harnesses have no plugin dispatch, so
the note becomes a plain instruction to read the agent soul or skill file.
Anything else in the body is copied byte for byte. A Note shape the renderer
does not recognise fails loudly instead of shipping a wrong render.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / "commands"
OPENCODE_DIR = REPO_ROOT / ".opencode" / "commands"
CURSOR_DIR = REPO_ROOT / ".cursor" / "commands"

# (pattern, replacement) pairs for the trailing **Note** line. \1 / \2 are the
# agent or skill slugs. Checked in order; the first match wins.
NOTE_RULES = [
    (
        re.compile(
            r"^This command dispatches the `forge-anything:([a-z0-9-]+)` agent "
            r"for the signal and the `forge-anything:([a-z0-9-]+)` agent for the "
            r"gate and execution\. No order goes out without the operator's "
            r"explicit approval for that exact order\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent (read `agents/{m.group(1)}/SOUL.md`) "
            f"for the signal and the `{m.group(2)}` agent "
            f"(read `agents/{m.group(2)}/SOUL.md`) for the gate and execution. "
            f"No order goes out without the operator's explicit approval for "
            f"that exact order."
        ),
    ),
    (
        re.compile(
            r"^This command dispatches the `forge-anything:([a-z0-9-]+)` agent "
            r"to run the release through `scripts/release\.sh`\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent (read `agents/{m.group(1)}/SOUL.md`) "
            f"and run the release through `scripts/release.sh`."
        ),
    ),
    (
        re.compile(
            r"^This command dispatches the `forge-anything:([a-z0-9-]+)` agent "
            r"with the security skills\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent (read `agents/{m.group(1)}/SOUL.md`) "
            f"with the security skills."
        ),
    ),
    (
        re.compile(
            r"^This command dispatches the `forge-anything:([a-z0-9-]+)` agent\. "
            r"This analyzes an existing video; /video produces one\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent (read `agents/{m.group(1)}/SOUL.md`). "
            f"This analyzes an existing video; /video produces one."
        ),
    ),
    (
        re.compile(
            r"^This command dispatches the `forge-anything:([a-z0-9-]+)` agent\. "
            r"The entry follows the Decision Log Template and lands in the owning "
            r"department's docs, with the agent's memory updated too\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent (read `agents/{m.group(1)}/SOUL.md`). "
            f"The entry follows the Decision Log Template and lands in the owning "
            f"department's docs, with the agent's memory updated too."
        ),
    ),
    (
        re.compile(
            r"^This command dispatches the `forge-anything:([a-z0-9-]+)` agent\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent: "
            f"read `agents/{m.group(1)}/SOUL.md` and follow it."
        ),
    ),
    (
        re.compile(
            r"^This command is powered by the `forge-anything:([a-z0-9-]+)` "
            r"and `(?:forge-anything:)?([a-z0-9-]+)` skills\.$"
        ),
        lambda m: (
            f"Use the `{m.group(1)}` skill (read `skills/{m.group(1)}/SKILL.md`) "
            f"and the `{m.group(2)}` skill (read `skills/{m.group(2)}/SKILL.md`)."
        ),
    ),
    (
        re.compile(
            r"^This command is powered by the `forge-anything:([a-z0-9-]+)` skill\.$"
        ),
        lambda m: (
            f"Use the `{m.group(1)}` skill: "
            f"read `skills/{m.group(1)}/SKILL.md` and follow it."
        ),
    ),
    (
        re.compile(
            r"^This command is powered by the `forge-anything:([a-z0-9-]+)` agent\.$"
        ),
        lambda m: (
            f"Act as the `{m.group(1)}` agent: "
            f"read `agents/{m.group(1)}/SOUL.md` and follow it."
        ),
    ),
]


def parse_command(path: Path) -> tuple[str, str, str]:
    """Return (name, description, body) for a commands/*.md source file."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n([\s\S]*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: missing YAML frontmatter")
    frontmatter, body = match.group(1), match.group(2)
    description = None
    for line in frontmatter.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "description":
            description = value.strip().strip("\"'")
    if not description:
        raise ValueError(f"{path}: missing frontmatter description")
    if '"' in description:
        raise ValueError(f"{path}: description contains a double quote")
    return path.stem, description, body.strip()


def rewrite_note(name: str, body: str) -> str:
    """Rewrite the trailing **Note** line for non-Claude harnesses."""
    lines = body.split("\n")
    note_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            note_idx = i
            break
    if note_idx is None:
        raise ValueError(f"commands/{name}.md: empty body")
    last = lines[note_idx]
    if not last.startswith("**Note**: "):
        return body
    note = last[len("**Note**: "):]
    for pattern, build in NOTE_RULES:
        match = pattern.match(note)
        if match:
            lines[note_idx] = "**Note**: " + build(match)
            rewritten = "\n".join(lines)
            break
    else:
        raise ValueError(
            f"commands/{name}.md: unrecognised Note shape, add a rule: {note!r}"
        )
    if "forge-anything:" in rewritten:
        raise ValueError(f"commands/{name}.md: rewrite left a forge-anything: ref")
    return rewritten


def check_refs(name: str, body: str) -> None:
    """Every agent/skill the rewritten body names must exist in the repo."""
    for slug in re.findall(r"`agents/([a-z0-9-]+)/SOUL\.md`", body):
        if not (REPO_ROOT / "agents" / slug / "SOUL.md").is_file():
            raise ValueError(f"commands/{name}.md: no such agent: {slug}")
    for slug in re.findall(r"`skills/([a-z0-9-]+)/SKILL\.md`", body):
        if not (REPO_ROOT / "skills" / slug / "SKILL.md").is_file():
            raise ValueError(f"commands/{name}.md: no such skill: {slug}")


def load_commands() -> list[dict]:
    commands = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        name, description, body = parse_command(path)
        if '"""' in body:
            raise ValueError(f"commands/{name}.md: body contains triple quotes")
        rewritten = rewrite_note(name, body)
        if "forge-anything:" in rewritten:
            raise ValueError(f"commands/{name}.md: body still has forge-anything:")
        check_refs(name, rewritten)
        commands.append(
            {"name": name, "description": description, "body": rewritten}
        )
    return commands


def render_toml(command: dict) -> str:
    return (
        f"description = \"{command['description']}\"\n"
        f"\n"
        f"prompt = \"\"\"\n"
        f"{command['body']}\n"
        f"\"\"\"\n"
    )


def render_opencode(command: dict) -> str:
    return (
        f"---\n"
        f"description: {command['description']}\n"
        f"---\n"
        f"\n"
        f"{command['body']}\n"
        f"\n"
        f"Operator input:\n"
        f"\n"
        f"$ARGUMENTS\n"
    )


def render_cursor(command: dict) -> str:
    return command["body"] + "\n"


def render_json(commands: list[dict]) -> str:
    payload = {
        "commands": [
            {
                "name": c["name"],
                "description": c["description"],
                "body": c["body"],
            }
            for c in commands
        ]
    }
    return json.dumps(payload, indent=2) + "\n"


def build_outputs(commands: list[dict]) -> dict[Path, str]:
    outputs = {COMMANDS_DIR / "rendered.json": render_json(commands)}
    for command in commands:
        outputs[COMMANDS_DIR / f"{command['name']}.toml"] = render_toml(command)
        outputs[OPENCODE_DIR / f"{command['name']}.md"] = render_opencode(command)
        outputs[CURSOR_DIR / f"{command['name']}.md"] = render_cursor(command)
    return outputs


def stale_files(wanted: set[Path]) -> list[Path]:
    stale = []
    for path in list(COMMANDS_DIR.glob("*.toml")) + list(
        OPENCODE_DIR.glob("*.md")
    ) + list(CURSOR_DIR.glob("*.md")):
        if path not in wanted:
            stale.append(path)
    return sorted(stale)


def main() -> None:
    check = "--check" in sys.argv[1:]
    commands = load_commands()
    outputs = build_outputs(commands)

    if check:
        problems = []
        for path, rendered in sorted(outputs.items()):
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != rendered:
                problems.append(str(path.relative_to(REPO_ROOT)))
        for path in stale_files(set(outputs)):
            problems.append(f"stale: {path.relative_to(REPO_ROOT)}")
        if problems:
            print("commands: rendered outputs out of sync with commands/*.md")
            for problem in problems:
                print(f"  {problem}")
            print("Run `python3 scripts/sync-commands.py`.")
            sys.exit(1)
        print(f"commands: {len(commands)} commands in sync across all harnesses")
        return

    for path, rendered in sorted(outputs.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    for path in stale_files(set(outputs)):
        path.unlink()
    print(
        f"commands: rendered {len(commands)} commands to "
        f"{len(outputs)} files "
        f"(commands/*.toml, commands/rendered.json, "
        f".opencode/commands/*.md, .cursor/commands/*.md)"
    )


if __name__ == "__main__":
    main()
