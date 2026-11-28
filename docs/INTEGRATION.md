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

## Install

### Claude Code

```bash
/plugin marketplace add galyarderlabs/forge-anything
/plugin install forge-anything@forge-anything-marketplace
```

Delivers the skills, commands, and the Forge Anything MCP server (`forge mcp`).

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

Delivers the skills and the Pi/OMP extension (`.pi/extensions/forge-anything.ts`), which injects the `using-forge-anything` bootstrap at session start and registers every Forge command as a native Pi slash command. OMP also auto-inherits skills installed for Claude Code and other harnesses.

### Codex

```bash
codex plugin marketplace add galyarderlabs/forge-anything
codex plugin add forge-anything@forge-anything
```

Delivers the skills (Codex reads the root `skills/` directly) and the Forge Anything MCP server (`forge mcp`). Codex has no slash-command system (custom prompts are deprecated and local-only), so Forge commands reach Codex through the MCP (`read_command`) and the skills, not as `/commands`.

### Cursor

In Cursor Agent chat:

```text
/add-plugin forge-anything
```

Or search for "forge-anything" in the plugin marketplace. Delivers the skills, the commands (`.cursor/commands/*.md`), and the MCP server.

### Antigravity

```bash
agy plugin install https://github.com/galyarderlabs/forge-anything
```

Delivers the skills, the commands (`commands/*.toml`), and the MCP server.

### OpenCode

Add forge-anything to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["forge-anything@git+https://github.com/galyarderlabs/forge-anything.git"]
}
```

Restart OpenCode. The plugin auto-installs and registers all skills and the MCP server, and the commands live in `.opencode/commands/*.md`. Full instructions: `.opencode/INSTALL.md`.

### GitHub Copilot CLI

```bash
copilot plugin marketplace add galyarderlabs/forge-anything
copilot plugin install forge-anything@forge-anything-marketplace
```

Delivers the skills, the commands (`.github/extensions/forge-anything/extension.mjs`), and the MCP server.

### Hermes Agent

Install Forge Anything as a Hermes plugin from this repository:

```bash
hermes plugins install galyarderlabs/forge-anything --enable
```

Restart any active Hermes sessions after installing. The plugin registers the skills with Hermes' native skill loader, registers every Forge command as a native Hermes slash command, and injects the `using-forge-anything` bootstrap on the first turn via the `pre_llm_call` hook. Note: Hermes has no post-compaction hook, so a very long session that compacts over its first turn loses the bootstrap - start a fresh session if skills stop triggering.

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

```text
Silo/
├── agents/             # Specialized Agents
├── skills/             # Strategic SOPs + Aesthetic Design
├── commands/           # Slash commands: *.md source, *.toml Antigravity renders, rendered.json
├── .opencode/commands/ # OpenCode command files
├── .cursor/commands/   # Cursor command files
├── .github/extensions/ # Copilot CLI slash-command extension
├── plugin.json         # Portable plugin manifest (Claude Code, Codex, Cursor, Copilot CLI)
├── .claude-plugin/     # Claude Code manifest
├── .codex-plugin/      # Codex manifest
├── .antigravity-plugin/ # Antigravity manifest
├── .hermes-plugin/     # Hermes manifest
└── .pi/                # Pi/OMP extension
```

## Context loading standard

Legacy context-bloat patterns have been removed so agents load only what they need. This keeps:
- **Context integrity**: lower noise and less unnecessary prompt surface.
- **Deterministic loads**: only the required instructions are loaded into the agent context.
