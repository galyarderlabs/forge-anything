import json
import os
import re
from pathlib import Path

BOOTSTRAP_MARKER = "forge-anything:using-forge-anything bootstrap for hermes"


def _skills_dir() -> str:
    """Locate the stock skills/ tree for either supported install layout.

    - git-clone install (`hermes plugins install galyarderlabs/forge-anything`): the plugin
      dir is the repo root, so `.hermes-plugin/` and `skills/` are siblings and
      this module resolves `../skills`.
    - flattened install (plugin files copied to the plugin dir root): `skills/`
      sits next to this module.

    Raises loudly when neither matches — a bootstrap that silently skips is how
    a broken install masquerades as a working one.
    """
    here = os.path.dirname(os.path.realpath(__file__))
    candidates = (
        os.path.realpath(os.path.join(here, "..", "skills")),
        os.path.realpath(os.path.join(here, "skills")),
    )
    for cand in candidates:
        if os.path.isfile(os.path.join(cand, "using-forge-anything", "SKILL.md")):
            return cand
    raise RuntimeError(
        "forge-anything plugin: cannot find the skills/ tree "
        f"(looked at {candidates}). Reinstall with "
        "`hermes plugins install galyarderlabs/forge-anything`."
    )


def _strip_frontmatter(content: str) -> str:
    match = re.match(r"^---\n[\s\S]*?\n---\n([\s\S]*)$", content)
    return (match.group(1) if match else content).strip()


def _frontmatter_value(content: str, key: str) -> str:
    """Return a flat ``key: value`` scalar from a SKILL.md frontmatter block.

    Hermes reads a skill's description from ``register_skill``'s ``description``
    argument, which defaults to "" — registering only the path left every stock
    skill with a blank description in the skill catalogue, so the model had
    nothing to select on. Stock frontmatter is a flat block of single-line
    scalars, so a line scan covers it without a YAML dependency.
    """
    match = re.match(r"^---\n([\s\S]*?)\n---\n", content)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        name, sep, value = line.partition(":")
        if sep and name.strip() == key:
            return value.strip().strip("\"'")
    return ""


def _build_bootstrap(skills_dir: str) -> str:
    with open(
        os.path.join(skills_dir, "using-forge-anything", "SKILL.md"),
        encoding="utf-8",
    ) as f:
        body = _strip_frontmatter(f.read())

    tools_path = os.path.join(
        skills_dir, "using-forge-anything", "references", "hermes-tools.md"
    )
    with open(tools_path, encoding="utf-8") as f:
        tool_mapping = f.read().strip()

    return (
        f"<EXTREMELY_IMPORTANT>\n"
        f"{BOOTSTRAP_MARKER}\n\n"
        f"You have Forge Anything.\n\n"
        f"The using-forge-anything skill below is already loaded for this "
        f"session. Follow it; do not load it again.\n\n"
        f"{body}\n\n"
        f"## Loading Skills on Hermes\n\n"
        f"Skills are registered with Hermes' native loader: "
        f'invoke one with `skill_view("forge-anything:skill-name")` '
        f'(for example `skill_view("forge-anything:brainstorming")`). '
        f"If a namespaced lookup returns 'not found', read the file "
        f"directly instead:\n"
        f'`read_file("{skills_dir}/skill-name/SKILL.md")`\n\n'
        f"Skills directory: `{skills_dir}`\n\n"
        f"{tool_mapping}\n"
        f"</EXTREMELY_IMPORTANT>"
    )


def _commands_file() -> str | None:
    """Locate commands/rendered.json for either supported install layout.

    Same two layouts as _skills_dir: the plugin dir is the repo root in a
    git-clone install, or the plugin files sit flattened in the plugin dir
    root. Returns None when the file is absent (an older checkout): commands
    are additive, so the plugin keeps working without them.
    """
    here = os.path.dirname(os.path.realpath(__file__))
    candidates = (
        os.path.realpath(os.path.join(here, "..", "commands", "rendered.json")),
        os.path.realpath(os.path.join(here, "commands", "rendered.json")),
    )
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None


def register(ctx):
    skills_dir = _skills_dir()
    bootstrap = _build_bootstrap(skills_dir)

    # Register every stock skill with Hermes' native loader so skill_view can
    # load them on demand. Standard markdown; no conversion (plugin guide).
    # register_skill requires a pathlib.Path — a str raises AttributeError and
    # hermes silently disables the whole plugin (Hermes plugin API behavior,
    # verified by the superpowers plugin 2026-07-23).
    for name in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, name, "SKILL.md")
        if os.path.isfile(skill_md):
            with open(skill_md, encoding="utf-8") as f:
                description = _frontmatter_value(f.read(), "description")
            ctx.register_skill(name, Path(skill_md), description=description)

    # Every Forge command as a native Hermes slash command. The bodies come
    # from commands/rendered.json (generated by scripts/sync-commands.py from
    # commands/*.md). The handler injects the body plus the operator's input
    # as a user message into the calling session, which starts the turn.
    commands_file = _commands_file()
    if commands_file is not None:
        with open(commands_file, encoding="utf-8") as f:
            rendered = json.load(f)
        for command in rendered["commands"]:
            name = command["name"]
            body = command["body"]

            def make_handler(body=body, name=name):
                def handle(args, session_key=None, **kwargs):
                    text = body
                    if args and args.strip():
                        text = f"{body}\n\nOperator input:\n\n{args.strip()}"
                    ok = ctx.inject_message(
                        text, role="user", session_key=session_key
                    )
                    if ok:
                        return f"Forge /{name} sent to the agent."
                    return f"Forge /{name} could not be injected into this session."

                return handle

            ctx.register_command(name, make_handler(), command["description"])

    # pre_llm_call returning {"context": ...} is the documented injection path
    # (on_session_start return values are ignored, and ctx.inject_message
    # refuses from that hook — Hermes plugin API behavior, verified by the
    # superpowers plugin 2026-07-23). The context is appended to the first
    # turn's user message. delegate_task children run with platform="subagent"
    # and an empty history, so every child's first turn would otherwise get
    # the controller bootstrap too.
    def pre_llm_call(
        session_id=None,
        user_message=None,
        conversation_history=None,
        is_first_turn=None,
        model=None,
        platform=None,
        **kwargs,
    ):
        if is_first_turn and platform != "subagent":
            return {"context": bootstrap}
        return None

    ctx.register_hook("pre_llm_call", pre_llm_call)
