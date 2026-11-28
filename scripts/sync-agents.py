#!/usr/bin/env python3
"""Render Forge Anything agents for every harness from agents/*/SOUL.md.

Usage:
  python3 scripts/sync-agents.py          # rewrite the rendered outputs
  python3 scripts/sync-agents.py --check  # exit 1 on drift, change nothing

The source is agents/<slug>/SOUL.md, the agent's judgment standard, plus
agents/<slug>/README.md for the short Purpose line. Every harness gets its
own native agent form from that one source:

  .claude/agents/<slug>.md      Claude Code (frontmatter name/description/
                                 skills; the manifest lists them explicitly)
  .cursor/agents/<slug>.md      Cursor (project subagents)
  .opencode/agents/<slug>.md    OpenCode (mode: subagent; the plugin also
                                 injects them as config.agents at runtime)
  .codex/agents/<slug>.toml     Codex (name/description/developer_instructions)
  .pi/agents/<slug>.md          Pi / OMP (project agents; Pi's extension API
                                 has no registerAgent, so files are the form)
  .github/agents/<slug>.agent.md Copilot CLI (project agents)
  .agents/agents/<slug>.md      Antigravity (workspace agents; the plugin
                                 manifest has no agents path field, and the
                                 plugin-root agents/ dir collides with the
                                 agent folders, so workspace scope is the form)

The body of every render is the SOUL.md verbatim: the soul IS the system
prompt. The description is the soul's identity line, the last paragraph of
## Vision, which always carries a "Use when" trigger; a soul without it fails
loudly instead of shipping a description that does not say when to delegate.
The skills roster comes from the trailing Skills: line; an agent with no
skills (six coordinators) gets no skills field in the Claude render.

This script also owns the MCP server declarations, so every harness points
at the same server (the `forge` CLI, stdio, local only):

  .mcp.json                      Claude Code (.mcp.json at the plugin root)
  mcp.json                       Agent Plugins 1.0.0 schema (OMP, Cursor)
  .cursor/mcp.json               Cursor project MCP config
  .codex/config.toml             Codex project MCP config
  .claude-plugin/plugin.json     the "agents" key (explicit paths; replaces
                                 the agents/ scan) -- updated in place
  .cursor-plugin/plugin.json     the Cursor plugin manifest (generated)

--check also verifies the MCP entries already declared elsewhere
(.codex-plugin/plugin.json, .antigravity-plugin/mcp_config.json,
.opencode/opencode.json) name the same server. Hermes has no agent
registration API (register_tool / register_hook / register_command only),
so Hermes agents stay the commands plus the soul files; nothing is rendered
for it and that is documented in docs/INTEGRATION.md, not hidden.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

CLAUDE_DIR = REPO_ROOT / ".claude" / "agents"
CURSOR_DIR = REPO_ROOT / ".cursor" / "agents"
OPENCODE_DIR = REPO_ROOT / ".opencode" / "agents"
CODEX_DIR = REPO_ROOT / ".codex" / "agents"
PI_DIR = REPO_ROOT / ".pi" / "agents"
COPILOT_DIR = REPO_ROOT / ".github" / "agents"
ANTIGRAVITY_WS_DIR = REPO_ROOT / ".agents" / "agents"

CLAUDE_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
CURSOR_MANIFEST = REPO_ROOT / ".cursor-plugin" / "plugin.json"

MCP_DESCRIPTION = (
    "Forge Anything MCP server: read the skills, agents, and commands, "
    "and scaffold a new Forge Anything project. Local-only, no network."
)
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

# MCP declarations that live elsewhere and must name the same server.
EXTERNAL_MCP = [
    REPO_ROOT / ".codex-plugin" / "plugin.json",
    REPO_ROOT / ".antigravity-plugin" / "mcp_config.json",
    REPO_ROOT / ".opencode" / "opencode.json",
]


def parse_agent(path: Path) -> dict:
    """Return (slug, description, skills, soul) for an agents/*/SOUL.md."""
    slug = path.parent.name
    soul = (path.parent / "SOUL.md").read_text(encoding="utf-8")
    match = re.search(r"^## Vision\n(.*?)(?=^## )", soul, re.M | re.S)
    if not match:
        raise ValueError(f"agents/{slug}/SOUL.md: no ## Vision section")
    paras = [p.strip() for p in match.group(1).strip().split("\n\n") if p.strip()]
    if not paras:
        raise ValueError(f"agents/{slug}/SOUL.md: empty ## Vision section")
    identity = paras[-1]
    if "Use when" not in identity:
        raise ValueError(
            f"agents/{slug}/SOUL.md: last Vision paragraph has no 'Use when'"
        )
    description = " ".join(identity.split())
    if '"' in description or "\\" in description:
        raise ValueError(
            f"agents/{slug}/SOUL.md: description has a quote or backslash"
        )
    skills_match = re.search(r"^Skills: (.+)$", soul, re.M)
    if not skills_match:
        raise ValueError(f"agents/{slug}/SOUL.md: no trailing Skills: line")
    skills = re.findall(r"`([a-z0-9-]+)`", skills_match.group(1))
    if '"""' in soul or "'''" in soul:
        raise ValueError(f"agents/{slug}/SOUL.md: soul has triple quotes")
    return {
        "slug": slug,
        "description": description,
        "skills": skills,
        "soul": soul,
    }


def load_agents() -> list[dict]:
    agents = []
    for path in sorted(AGENTS_DIR.glob("*/SOUL.md")):
        agents.append(parse_agent(path))
    if len(agents) != 54:
        raise ValueError(f"expected 54 agents, found {len(agents)}")
    return agents


def yaml_double_quoted(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_md(agent: dict, frontmatter: str) -> str:
    return f"---\n{frontmatter}---\n\n{agent['soul']}"


def render_claude(agent: dict) -> str:
    lines = [
        f"name: {agent['slug']}",
        f"description: {yaml_double_quoted(agent['description'])}",
    ]
    if agent["skills"]:
        lines.append("skills:")
        lines.extend(f"  - {skill}" for skill in agent["skills"])
    return render_md(agent, "\n".join(lines) + "\n")


def render_cursor(agent: dict) -> str:
    return render_md(
        agent,
        f"name: {agent['slug']}\n"
        f"description: {yaml_double_quoted(agent['description'])}\n",
    )


def render_opencode(agent: dict) -> str:
    return render_md(
        agent,
        f"description: {yaml_double_quoted(agent['description'])}\n"
        f"mode: subagent\n",
    )


def render_pi(agent: dict) -> str:
    return render_cursor(agent)


def render_copilot(agent: dict) -> str:
    return render_cursor(agent)


def render_antigravity_ws(agent: dict) -> str:
    return render_cursor(agent)


def render_codex(agent: dict) -> str:
    return (
        f"name = \"{agent['slug']}\"\n"
        f"description = \"{agent['description']}\"\n"
        f"developer_instructions = '''\n"
        f"{agent['soul']}'''\n"
    )


def mcp_server_entry() -> dict:
    return {
        "args": ["mcp"],
        "command": "forge",
        "description": MCP_DESCRIPTION,
        "type": "stdio",
    }


def render_mcp_claude() -> str:
    return json.dumps({"mcpServers": {"forge-anything": mcp_server_entry()}},
                      indent=4, sort_keys=True) + "\n"


def render_mcp_plugins() -> str:
    return json.dumps(
        {
            "$schema": MCP_SCHEMA,
            "mcpServers": {"forge-anything": mcp_server_entry()},
        },
        indent=4,
        sort_keys=True,
    ) + "\n"


def render_mcp_cursor() -> str:
    return render_mcp_claude()


def render_mcp_codex() -> str:
    return (
        "[mcp_servers.forge-anything]\n"
        "command = \"forge\"\n"
        "args = [\"mcp\"]\n"
        f"description = \"{MCP_DESCRIPTION}\"\n"
    )


def render_cursor_manifest(version: str) -> str:
    manifest = {
        "agents": "./.cursor/agents",
        "author": {
            "name": "Galyarder Labs",
            "url": "https://galyarderlabs.com",
        },
        "commands": "./.cursor/commands",
        "description": "Forge anything with AI agents.",
        "homepage": "https://github.com/galyarderlabs/forge-anything",
        "hooks": "hooks/hooks-cursor.json",
        "license": "GPL-3.0-or-later",
        "mcpServers": "./mcp.json",
        "name": "forge-anything",
        "repository": "https://github.com/galyarderlabs/forge-anything",
        "skills": "./skills",
        "version": version,
    }
    return json.dumps(manifest, indent=4, sort_keys=True) + "\n"


def build_outputs(agents: list[dict]) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for agent in agents:
        slug = agent["slug"]
        outputs[CLAUDE_DIR / f"{slug}.md"] = render_claude(agent)
        outputs[CURSOR_DIR / f"{slug}.md"] = render_cursor(agent)
        outputs[OPENCODE_DIR / f"{slug}.md"] = render_opencode(agent)
        outputs[CODEX_DIR / f"{slug}.toml"] = render_codex(agent)
        outputs[PI_DIR / f"{slug}.md"] = render_pi(agent)
        outputs[COPILOT_DIR / f"{slug}.agent.md"] = render_copilot(agent)
        outputs[ANTIGRAVITY_WS_DIR / f"{slug}.md"] = render_antigravity_ws(agent)
    outputs[REPO_ROOT / ".mcp.json"] = render_mcp_claude()
    outputs[REPO_ROOT / "mcp.json"] = render_mcp_plugins()
    outputs[REPO_ROOT / ".cursor" / "mcp.json"] = render_mcp_cursor()
    outputs[REPO_ROOT / ".codex" / "config.toml"] = render_mcp_codex()
    version = json.loads((REPO_ROOT / "package.json").read_text())["version"]
    outputs[CURSOR_MANIFEST] = render_cursor_manifest(version)
    return outputs


def claude_manifest_agents(agents: list[dict]) -> list[str]:
    return [f"./.claude/agents/{a['slug']}.md" for a in agents]


def check_external_mcp() -> list[str]:
    """Every MCP declaration elsewhere must name the same forge server."""
    problems = []
    for path in EXTERNAL_MCP:
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "opencode.json":
            server = data["mcp"]["forge-anything"]
            command, args = server["command"][0], server["command"][1:]
        else:
            server = data["mcpServers"]["forge-anything"]
            command, args = server["command"], server["args"]
        if command != "forge" or args != ["mcp"]:
            problems.append(
                f"{path.relative_to(REPO_ROOT)}: MCP server is not "
                f"`forge mcp` ({command} {args})"
            )
    return problems


def check_renders(outputs: dict[Path, str]) -> list[str]:
    problems = []
    for path, rendered in sorted(outputs.items()):
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != rendered:
            problems.append(str(path.relative_to(REPO_ROOT)))
    return problems


def check_stale(wanted: set[Path]) -> list[str]:
    stale = []
    for directory, pattern in [
        (CLAUDE_DIR, "*.md"),
        (CURSOR_DIR, "*.md"),
        (OPENCODE_DIR, "*.md"),
        (CODEX_DIR, "*.toml"),
        (PI_DIR, "*.md"),
        (COPILOT_DIR, "*.agent.md"),
        (ANTIGRAVITY_WS_DIR, "*.md"),
    ]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob(pattern)):
            if path not in wanted:
                stale.append(f"stale: {path.relative_to(REPO_ROOT)}")
    return stale


def check_toml_parses(agents: list[dict]) -> list[str]:
    problems = []
    for agent in agents:
        path = CODEX_DIR / f"{agent['slug']}.toml"
        if not path.exists():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            problems.append(f".codex/agents/{agent['slug']}.toml: {exc}")
            continue
        if data.get("name") != agent["slug"]:
            problems.append(f".codex/agents/{agent['slug']}.toml: wrong name")
        if data.get("description") != agent["description"]:
            problems.append(
                f".codex/agents/{agent['slug']}.toml: wrong description"
            )
        if data.get("developer_instructions", "").strip() != agent["soul"].strip():
            problems.append(
                f".codex/agents/{agent['slug']}.toml: instructions are not the soul"
            )
    return problems


def main() -> None:
    check = "--check" in sys.argv[1:]
    agents = load_agents()
    outputs = build_outputs(agents)

    if check:
        problems = check_renders(outputs)
        problems += check_stale(set(outputs))
        problems += check_toml_parses(agents)
        problems += check_external_mcp()
        manifest = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
        if manifest.get("agents") != claude_manifest_agents(agents):
            problems.append(".claude-plugin/plugin.json: agents key out of sync")
        if problems:
            print("agents: rendered outputs out of sync with agents/*/SOUL.md")
            for problem in problems:
                print(f"  {problem}")
            print("Run `python3 scripts/sync-agents.py`.")
            sys.exit(1)
        print(f"agents: {len(agents)} agents in sync across all harnesses")
        return

    for path, rendered in sorted(outputs.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    for problem in check_stale(set(outputs)):
        Path(REPO_ROOT / problem.removeprefix("stale: ").strip()).unlink()
    manifest = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
    manifest["agents"] = claude_manifest_agents(agents)
    CLAUDE_MANIFEST.write_text(
        json.dumps(manifest, indent=4, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"agents: rendered {len(agents)} agents to {len(outputs)} files "
        f"(.claude/agents, .cursor/agents, .opencode/agents, .codex/agents, "
        f".pi/agents, .github/agents, .agents/agents, plus MCP configs and "
        f"the Cursor manifest)"
    )


if __name__ == "__main__":
    main()
