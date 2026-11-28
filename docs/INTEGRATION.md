# Multi-Platform Integration Protocol

Forge Anything is a host-agnostic system of rules and workflows for AI agents, for work and for life. Everything installs via plugin, no manual setup, no scripts, no clone-and-symlink.

## Supported Platforms

The framework ships native plugins for these harnesses:

1.  **Claude Code**: Advanced CLI marketplace integration.
2.  **OMP/Pi (Oh My Pi)**: Native Pi extension; OMP is a fork of Pi.
3.  **OpenAI Codex**: Native plugin; Codex reads the root `skills/` directly.
4.  **Cursor**: Native plugin (portable root `plugin.json`).
5.  **Antigravity**: Native plugin.
6.  **OpenCode**: Specialized plugin ecosystem.
7.  **GitHub Copilot CLI**: Native plugin (portable root `plugin.json`).
8.  **Hermes Agent**: Local-first autonomous assistant runtime. Hermes is our own agent, always a target.

## Feature matrix

Every harness gets every feature: skills, agents, commands, hooks, CLI
access, and MCP. Where a vendor has no native form for a feature, the table
says what the equivalent is, and where there is no equivalent it says so.
Nothing is silently missing.

| Feature | Claude Code | OMP / Pi | Codex | Cursor | Antigravity | OpenCode | Copilot CLI | Hermes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Skills | manifest | extension + package.json | manifest | manifest | manifest path | plugin config | spec discovery | native loader |
| Agents | `.claude/agents/` via manifest | `.omp/agents/` native + `.pi/agents/` files, `/agent` command | `.codex/agents/*.toml` | `.cursor/agents/` via manifest | workspace `.agents/agents/` only | `.opencode/agents/` + config injection | `.github/agents/` project files | `/agent` command via `delegate_task` |
| Commands | `commands/*.md` | extension `registerCommand` | via MCP + skills (no slash system) | `.cursor/commands/` | `commands/*.toml` | `.opencode/commands/` | extension `joinSession` | `ctx.register_command` |
| Hooks | `hooks/hooks.json` | extension lifecycle | `.codex/hooks.json` SessionStart | `hooks/hooks-cursor.json` | root `hooks.json` | message transform (per-message bootstrap) | `.github/hooks/` | `pre_llm_call` |
| MCP | `.mcp.json` | root `mcp.json` | inline in plugin | `mcp.json` via manifest | `mcp_config.json` | `opencode.json` | root `mcp.json` (spec) | n/a, native plugin |
| CLI | `forge` on PATH (install.sh) | same | same | same | same | same | same | same |

The rule behind the table: where a harness has no native place for
agents, a command or hook spawns a subagent that reads the project's
`agents/<slug>/` folder, soul plus memory, instead of pretending the
feature does not exist. Pi core discovers `.omp/agents/` itself and
spawns them with the built-in `task` tool, so no third-party subagent
extension is needed; Hermes has no agent registry, so the plugin's
`/agent` command spawns them through `delegate_task`, the native
subagent mechanism.

Gaps, stated plainly: Codex hooks ship in `.codex/hooks.json`
(SessionStart runs `hooks/session-start codex`), but firing them live
is still unproven: no Codex credentials on this machine, so the canary
run needs the operator's login (or `--dangerously-bypass-hook-trust`
for a one-off). The hook file is repo content; the login is only the
test, not the wiring. Antigravity agents ship at workspace scope only
(`.agents/agents/` in scaffolded projects): the plugin manifest has no
agents path field, and the only plugin-root agents dir collides with
the agent folders. Copilot plugin-scope agents are unverified (the SDK
shape is not confirmed), so Copilot agents ship as project files.

## Install

The MCP server in every harness calls the `forge` CLI (bare `forge` on
PATH), so install it first. Without it the MCP configs fail and the
commands that shell out to `forge` do nothing.

```bash
curl -fsSL https://raw.githubusercontent.com/galyarderlabs/forge-anything/main/install.sh | sh
```

Then install the plugin for your harness.

### Claude Code

```bash
/plugin marketplace add galyarderlabs/forge-anything
/plugin install forge-anything@forge-anything-marketplace
```

Delivers the skills, the agents (`.claude/agents/`, listed explicitly in
the plugin manifest), the commands, and the Forge Anything MCP server
(`forge mcp`).

### OMP / Pi

Pi:

```bash
pi install git:github.com/galyarderlabs/forge-anything
```

OMP (a fork of Pi - same plugin, OMP marketplace commands):

```bash
omp plugin marketplace add galyarderlabs/forge-anything
omp plugin install forge-anything@forge-anything-marketplace
```

Delivers the skills, the agents (`.omp/agents/` project files, discovered by Pi core and spawned with the `task` tool, plus `.pi/agents/` for third-party subagent extensions), and the
Pi/OMP extension (`.pi/extensions/forge-anything.ts`), which injects the `using-forge-anything` bootstrap at session start, registers every Forge command as a native Pi slash command, and adds `/agent <slug> <goal>` to spawn any Forge agent as a subagent. OMP also auto-inherits skills installed for Claude Code and other harnesses.

### Codex

```bash
codex plugin marketplace add galyarderlabs/forge-anything
codex plugin add forge-anything@forge-anything
```

Delivers the skills (Codex reads the root `skills/` directly), the agents
(`.codex/agents/*.toml`), and the Forge Anything MCP server (`forge mcp`). Codex has no slash-command system (custom prompts are deprecated and local-only), so Forge commands reach Codex through the MCP (`read_command`) and the skills, not as `/commands`.

### Cursor

In Cursor Agent chat:

```text
/add-plugin forge-anything
```

Or search for "forge-anything" in the plugin marketplace. Delivers the skills, the agents (`.cursor/agents/`, wired through `.cursor-plugin/plugin.json`), the commands (`.cursor/commands/*.md`), and the MCP server.

### Antigravity

```bash
agy plugin install https://github.com/galyarderlabs/forge-anything
```

Delivers the skills, the agents (`.codex/agents/*.toml`), the MCP server, and the SessionStart hook (`.codex/hooks.json` runs `hooks/session-start codex` at session start). Commands reach Codex through the MCP (`read_command`) and the skills, since Codex has no slash-command system.

### OpenCode

Add forge-anything to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["forge-anything@git+https://github.com/galyarderlabs/forge-anything.git"]
}
```

Restart OpenCode. The plugin auto-installs and registers all skills, all agents (as native subagents through `config.agents`, rendered from `.opencode/agents/*.md`), and the MCP server, and the commands live in `.opencode/commands/*.md`. Full instructions: `.opencode/INSTALL.md`.

### GitHub Copilot CLI

```bash
copilot plugin marketplace add galyarderlabs/forge-anything
copilot plugin install forge-anything@forge-anything-marketplace
```

Delivers the skills, the agents (`.github/agents/` project files), the commands (`.github/extensions/forge-anything/extension.mjs`), and the MCP server.

### Hermes Agent

Install Forge Anything as a Hermes plugin from this repository:

```bash
hermes plugins install galyarderlabs/forge-anything --enable
```

Restart any active Hermes sessions after installing. The plugin registers the skills with Hermes' native skill loader, registers every Forge command as a native Hermes slash command, and injects the `using-forge-anything` bootstrap on the first turn via the `pre_llm_call` hook. Agents run through the `/agent` command: `/agent <slug> <goal>` spawns that Forge agent as a native subagent via `delegate_task`, reading its soul and memory from `agents/<slug>/`. Note: Hermes has no post-compaction hook, so a very long session that compacts over its first turn loses the bootstrap - start a fresh session if skills stop triggering.

## Skills only (no harness plugin)

If you only want the skills, without a harness plugin:

```bash
npx skills add galyarderlabs/forge-anything
```

This installs the skills into the harness of your choice (project or global scope).

## Company packages

To bring an existing agent-company package into a project:

```bash
forge company import --from <path> [dir]
```

This validates the package (`COMPANY.md` with `agentcompanies/v1` frontmatter) and copies it self-contained into `company/<slug>/`. See [company-import.md](company-import.md) for the full reference.

## Command Silo Structure (Universal Architecture)

The repository is organized into 17 departments. Skills and agents live flat so every supported harness can read them. Commands start from one source, `commands/*.md` (the Claude Code slash-command format), and `scripts/sync-commands.py` renders every harness's native form from it (`--check` in CI keeps the renders in sync). Each harness gets the commands in its own form:

- **Claude Code:** `commands/*.md`, wired through `.claude-plugin/plugin.json`.
- **Pi / OMP:** `.pi/extensions/forge-anything.ts` reads `commands/rendered.json` and registers each command with `registerCommand`.
- **OpenCode:** `.opencode/commands/*.md`, frontmatter plus the body as the prompt template.
- **Cursor:** `.cursor/commands/*.md`, plain prompt files.
- **Antigravity:** `commands/*.toml`, description plus prompt.
- **Copilot CLI:** `.github/extensions/forge-anything/extension.mjs` reads `commands/rendered.json` and registers each command with the extension SDK.
- **Hermes:** `.hermes-plugin/__init__.py` reads `commands/rendered.json` and registers each command with `ctx.register_command`.
- **Codex:** no render. Codex has no slash-command system (custom prompts are deprecated and local-only), so commands reach Codex through the MCP (`read_command`) and the skills.

The renders rewrite one line: the trailing `**Note**` that names a `forge-anything:` agent or skill becomes a plain instruction to read the agent soul or skill file, because other harnesses have no plugin dispatch. Everything else in the body is copied unchanged.

## Agent delivery

Agents start from one source, `agents/<slug>/SOUL.md`, and `scripts/sync-agents.py` renders every harness's native form from it (`--check` in CI keeps the renders in sync). The body of every render is the soul verbatim: the soul is the system prompt. The description is the soul's identity line, the last paragraph of `## Vision`, which always carries a `Use when` trigger; a soul without it fails the render instead of shipping a description that does not say when to delegate. The skills roster comes from the trailing `Skills:` line; the six coordinators with no skills get no skills field in the Claude render.

- **Claude Code:** `.claude/agents/<slug>.md`, frontmatter name/description/skills. The manifest lists all 54 explicitly under the `agents` key, which replaces the `agents/` scan.
- **Pi / OMP:** `.omp/agents/<slug>.md` project files, discovered by Pi core itself and spawned with the built-in `task` tool by name. The extension adds a `/agent <slug> <goal>` command that does the spawn in one command. `.pi/agents/<slug>.md` holds the same definitions in the form third-party subagent extensions read; `.claude/agents/` is also read by them as a fallback.
- **OpenCode:** `.opencode/agents/<slug>.md`, frontmatter description plus `mode: subagent`. The plugin also injects them at runtime as `config.agents`, so they are native subagents without reading files.
- **Cursor:** `.cursor/agents/<slug>.md` project subagents, wired through `.cursor-plugin/plugin.json` (explicit paths replace folder discovery).
- **Antigravity:** `.agents/agents/<slug>.md` workspace agents, seeded by the scaffold. The plugin manifest has no agents path field, and the only plugin-root agents dir collides with the agent folders, so there is no plugin-scope agent form.
- **Copilot CLI:** `.github/agents/<slug>.agent.md` project agents. Plugin-scope agents through the extension SDK are unverified, so they are not shipped.
- **Hermes:** no render. Hermes has no agent registry, so the plugin's `/agent <slug> <goal>` command spawns the agent as a native subagent through `delegate_task`, reading its soul and memory from `agents/<slug>/`.
- **Codex:** `.codex/agents/<slug>.toml`, with the soul as `developer_instructions`.

## MCP server

One server, declared everywhere in the same shape: the `forge` CLI over stdio, local only, no network, command `forge`, args `["mcp"]`. `scripts/sync-agents.py` owns the declarations and `--check` verifies the ones that live elsewhere name the same server.

- **Claude Code:** `.mcp.json` at the plugin root (the manifest pointed at it before the file existed; that dangling reference is fixed now).
- **OMP / Pi:** `mcp.json` at the repo root, Agent Plugins 1.0.0 schema.
- **Cursor:** `mcp.json` through `.cursor-plugin/plugin.json`, plus `.cursor/mcp.json` in scaffolded projects.
- **Antigravity:** `.antigravity-plugin/mcp_config.json`.
- **OpenCode:** the `mcp` block in `.opencode/opencode.json`.
- **Codex:** inline `mcpServers` in `.codex-plugin/plugin.json`, plus `.codex/config.toml` in scaffolded projects.
- **Copilot CLI:** root `mcp.json` under the Agent Plugins 1.0.0 schema.
- **Hermes:** n/a, native plugin.

Scaffolded projects get the project configs (`.mcp.json`, `mcp.json`, `.cursor/mcp.json`, `.codex/config.toml`, `.opencode/opencode.json`) so the MCP works in every harness that reads project config. All of them call bare `forge`, so the CLI prerequisite at the top of Install applies to projects too.

```text
Silo/
├── agents/             # Specialized Agents
├── skills/             # Strategic SOPs + Aesthetic Design
├── commands/           # Slash commands: *.md source, *.toml Antigravity renders, rendered.json
├── .claude/agents/     # Claude Code agents (manifest lists them explicitly)
├── .cursor/agents/     # Cursor project subagents
├── .opencode/agents/   # OpenCode agents (mode: subagent)
├── .codex/agents/      # Codex agents (*.toml)
├── .pi/agents/         # Pi / OMP project agents (third-party subagent extensions)
├── .omp/agents/         # Pi / OMP core project agents (task tool)
├── .github/agents/     # Copilot CLI project agents
├── .agents/agents/     # Antigravity workspace agents
├── .codex/hooks.json    # Codex SessionStart hook
├── hooks/session-start  # SessionStart script (Claude, Codex, Antigravity)
├── .opencode/commands/ # OpenCode command files
├── .cursor/commands/   # Cursor command files
├── .github/extensions/ # Copilot CLI slash-command extension
├── .mcp.json           # Claude Code MCP server
├── mcp.json            # Agent Plugins 1.0.0 MCP server (OMP, Cursor, Copilot)
├── plugin.json         # Portable plugin manifest (Claude Code, Codex, Cursor, Copilot CLI)
├── .claude-plugin/     # Claude Code manifest
├── .codex-plugin/      # Codex manifest
├── .cursor-plugin/     # Cursor manifest
├── .antigravity-plugin/ # Antigravity manifest
├── .hermes-plugin/     # Hermes manifest
└── .pi/                # Pi/OMP extension
```

## Context loading standard

Legacy context-bloat patterns have been removed so agents load only what they need. This keeps:
- **Context integrity**: lower noise and less unnecessary prompt surface.
- **Deterministic loads**: only the required instructions are loaded into the agent context.
