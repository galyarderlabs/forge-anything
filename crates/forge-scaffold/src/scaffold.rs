//! The scaffold itself: drop a tidy Forge Anything repo into a folder.
//!
//! What lands in the target directory:
//! - `README.md`, `AGENTS.md`, `WORKFLOW.md`, `.gitignore`, `skills.json`
//! - `skills/<curated>/` - the curated skills, copied whole from the source
//! - `agents/<curated>/` - the curated agents (SOUL.md + MEMORY.md + README.md)
//! - `commands/` - all slash commands (`.md` source plus the Antigravity
//!   `.toml` renders and `rendered.json`)
//! - `.opencode/commands/` and `.cursor/commands/` - the same commands in
//!   each harness's native file form
//! - `.claude/agents/`, `.cursor/agents/`, `.opencode/agents/`,
//!   `.codex/agents/`, `.pi/agents/`, `.github/agents/`, `.agents/agents/`
//!   - the curated agents in each harness's native form
//! - `.mcp.json`, `mcp.json`, `.cursor/mcp.json`, `.codex/config.toml`,
//!   `.opencode/opencode.json` - the project MCP configs, so the `forge`
//!   MCP server works in every harness that reads project config
//! - `.github/extensions/forge-anything/extension.mjs` - the Copilot CLI
//!   slash-command extension
//! - `docs/` - specs, plans, reports, templates, design, and the 17
//!   departments with a README and an audit template each
//!
//! Skills stay host-agnostic: any agent or host reads `skills/` straight
//! from the project folder. Commands and agents are the exception: each
//! harness has its own native form for them, so the scaffold seeds every
//! form. The full `integrations/` tree stays in the Forge Anything repo
//! itself; the scaffold ships only what a new project needs to work.

use crate::curated;
use std::fs;
use std::path::{Path, PathBuf};

/// How many things the scaffold wrote, for the final report.
#[derive(Debug, Default)]
pub struct Summary {
    pub skills: usize,
    pub agents: usize,
    pub commands: usize,
    pub design_specs: usize,
    pub files: usize,
}

impl Summary {
    fn note_file(&mut self) {
        self.files += 1;
    }
}

/// Scaffold `source` into `target`.
///
/// `target` must not exist, or must be empty, unless `force` is set.
/// `project_name` is used in the generated README; it defaults to the
/// target directory's file name when empty.
pub fn scaffold(
    source: &Path,
    target: &Path,
    project_name: &str,
    force: bool,
) -> Result<Summary, String> {
    // Refuse to clobber a non-empty directory unless forced.
    if target.exists() {
        if !target.is_dir() {
            return Err(format!(
                "target '{}' exists and is not a directory",
                target.display()
            ));
        }
        let non_empty = fs::read_dir(target)
            .map_err(|e| format!("cannot read target '{}': {e}", target.display()))?
            .next()
            .is_some();
        if non_empty && !force {
            return Err(format!(
                "target '{}' is not empty; pass --force to scaffold into it anyway",
                target.display()
            ));
        }
    } else {
        fs::create_dir_all(target)
            .map_err(|e| format!("cannot create target '{}': {e}", target.display()))?;
    }

    let mut s = Summary::default();
    let name = if project_name.is_empty() {
        target
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "my-project".to_string())
    } else {
        project_name.to_string()
    };

    // --- Top-level docs -------------------------------------------------
    copy_file(source.join("AGENTS.md"), target.join("AGENTS.md"), &mut s)?;
    copy_file(
        source.join("WORKFLOW.md"),
        target.join("WORKFLOW.md"),
        &mut s,
    )?;
    write_file(target.join("README.md"), &readme(&name), &mut s)?;
    write_file(target.join(".gitignore"), GITIGNORE, &mut s)?;
    write_file(target.join("skills.json"), &skills_manifest(), &mut s)?;

    // --- Curated skills -------------------------------------------------
    for skill in curated::CURATED_SKILLS {
        let src = source.join("skills").join(skill);
        let dst = target.join("skills").join(skill);
        if !src.join("SKILL.md").is_file() {
            return Err(format!("source is missing skills/{skill}/SKILL.md"));
        }
        copy_dir(&src, &dst, &mut s)?;
        s.skills += 1;
    }

    // --- Curated agents -------------------------------------------------
    for agent in curated::CURATED_AGENTS {
        let src = source.join("agents").join(agent);
        let dst = target.join("agents").join(agent);
        if !src.join("SOUL.md").is_file() {
            return Err(format!("source is missing agents/{agent}/SOUL.md"));
        }
        copy_dir(&src, &dst, &mut s)?;
        s.agents += 1;
    }

    // --- All slash commands ---------------------------------------------
    // The .md files are the Claude Code source; the .toml files are the
    // Antigravity renders and rendered.json feeds Pi, Hermes, and Copilot
    // CLI at runtime. All three come from scripts/sync-commands.py.
    let commands_src = source.join("commands");
    let commands_dst = target.join("commands");
    for entry in read_dir_sorted(&commands_src)? {
        let path = entry.path();
        let is_md = path.extension().is_some_and(|e| e == "md");
        let is_toml = path.extension().is_some_and(|e| e == "toml");
        if is_md || is_toml {
            let name = entry.file_name().to_string_lossy().into_owned();
            copy_file(path, commands_dst.join(name), &mut s)?;
            if is_md {
                s.commands += 1;
            }
        }
    }
    let rendered = commands_src.join("rendered.json");
    if rendered.is_file() {
        copy_file(rendered, commands_dst.join("rendered.json"), &mut s)?;
    }

    // --- Per-harness command copies -------------------------------------
    // Commands ship in every harness's native form. The sources are the
    // renders in this repo (scripts/sync-commands.py); the scaffold seeds
    // them so a new project has working slash commands everywhere. A source
    // without the renders still scaffolds; CI's sync-commands --check is
    // what guarantees the renders exist in the Forge Anything repo.
    for (src_dir, dst_dir) in [
        (
            source.join(".opencode").join("commands"),
            target.join(".opencode").join("commands"),
        ),
        (
            source.join(".cursor").join("commands"),
            target.join(".cursor").join("commands"),
        ),
    ] {
        if !src_dir.is_dir() {
            continue;
        }
        for entry in read_dir_sorted(&src_dir)? {
            let path = entry.path();
            if path.extension().is_some_and(|e| e == "md") {
                let name = entry.file_name().to_string_lossy().into_owned();
                copy_file(path, dst_dir.join(name), &mut s)?;
            }
        }
    }
    let copilot_ext = source
        .join(".github")
        .join("extensions")
        .join("forge-anything")
        .join("extension.mjs");
    if copilot_ext.is_file() {
        copy_file(
            copilot_ext,
            target
                .join(".github")
                .join("extensions")
                .join("forge-anything")
                .join("extension.mjs"),
            &mut s,
        )?;
    }

    // --- Per-harness agent copies ---------------------------------------
    // Agents ship in every harness's native form, the same way commands do.
    // The sources are the renders in this repo (scripts/sync-agents.py);
    // the scaffold seeds the curated agents only, matching agents/ itself.
    // A source without the renders still scaffolds; CI's sync-agents
    // --check is what guarantees the renders exist in the Forge Anything
    // repo.
    for agent in curated::CURATED_AGENTS {
        for (src_dir, dst_dir, file_name) in [
            (
                source.join(".claude").join("agents"),
                target.join(".claude").join("agents"),
                format!("{agent}.md"),
            ),
            (
                source.join(".cursor").join("agents"),
                target.join(".cursor").join("agents"),
                format!("{agent}.md"),
            ),
            (
                source.join(".opencode").join("agents"),
                target.join(".opencode").join("agents"),
                format!("{agent}.md"),
            ),
            (
                source.join(".codex").join("agents"),
                target.join(".codex").join("agents"),
                format!("{agent}.toml"),
            ),
            (
                source.join(".pi").join("agents"),
                target.join(".pi").join("agents"),
                format!("{agent}.md"),
            ),
            (
                source.join(".github").join("agents"),
                target.join(".github").join("agents"),
                format!("{agent}.agent.md"),
            ),
            (
                source.join(".agents").join("agents"),
                target.join(".agents").join("agents"),
                format!("{agent}.md"),
            ),
        ] {
            let src_file = src_dir.join(&file_name);
            if src_file.is_file() {
                copy_file(src_file, dst_dir.join(&file_name), &mut s)?;
            }
        }
    }

    // --- Project MCP configs --------------------------------------------
    // The `forge` MCP server, in every harness's project config form, so a
    // new project gets the MCP in Claude Code, OMP, Cursor, Codex, and
    // OpenCode without installing anything else first. The CLI itself is
    // still a prerequisite: these configs call bare `forge`, so the
    // operator runs install.sh before the server can start.
    for (src_file, dst_file) in [
        (source.join(".mcp.json"), target.join(".mcp.json")),
        (source.join("mcp.json"), target.join("mcp.json")),
        (
            source.join(".cursor").join("mcp.json"),
            target.join(".cursor").join("mcp.json"),
        ),
        (
            source.join(".codex").join("config.toml"),
            target.join(".codex").join("config.toml"),
        ),
        (
            source.join(".opencode").join("opencode.json"),
            target.join(".opencode").join("opencode.json"),
        ),
    ] {
        if src_file.is_file() {
            copy_file(src_file, dst_file, &mut s)?;
        }
    }

    // --- Docs structure --------------------------------------------------
    for d in ["specs", "plans", "reports", "templates", "design"] {
        fs::create_dir_all(target.join("docs").join(d))
            .map_err(|e| format!("cannot create docs/{d}: {e}"))?;
    }
    // Decision log template -> docs/reports/.
    let decision_log = source
        .join("docs/templates")
        .join(curated::DECISION_LOG_TEMPLATE);
    if decision_log.is_file() {
        copy_file(
            decision_log,
            target
                .join("docs/reports")
                .join(curated::DECISION_LOG_TEMPLATE),
            &mut s,
        )?;
    }
    // The design guide is the scaffold seed: root DESIGN.md -> docs/design/.
    let design_guide = source.join("DESIGN.md");
    if design_guide.is_file() {
        copy_file(
            design_guide,
            target.join("docs/design").join("DESIGN.md"),
            &mut s,
        )?;
        s.design_specs += 1;
    }
    // Departments: README + audit template each.
    for dept in curated::DEPARTMENTS {
        let dept_dir = target.join("docs/departments").join(dept);
        fs::create_dir_all(&dept_dir)
            .map_err(|e| format!("cannot create docs/departments/{dept}: {e}"))?;
        write_file(dept_dir.join("README.md"), &department_readme(dept), &mut s)?;
        if let Some(template) = curated::audit_template_for(dept) {
            let src = source.join("docs/templates").join(template);
            if src.is_file() {
                copy_file(src, dept_dir.join(template), &mut s)?;
            }
        }
    }

    Ok(s)
}

/// The generated README for a scaffolded repo.
fn readme(project_name: &str) -> String {
    format!(
        "# {project_name}\n\
         \n\
         A Forge Anything project: an AI agent already knows the rules, the\n\
         workflow, and where to put its work.\n\
         \n\
         ## Structure\n\
         \n\
         - `skills/` - the curated Forge Anything skills (reusable AI-agent\n\
         rules). `using-forge-anything` is the entry point; the rest cover\n\
         the core loop (plan, build, verify, ship) and the seventeen\n\
         departments.\n\
         - `agents/` - the Forge agents plus the lead role agent per\n\
         department.\n\
         - `commands/` - slash commands (`/plan`, `/docs`, `/release`, ...),\n\
         rendered for every harness: `commands/*.toml` (Antigravity),\n\
         `.opencode/commands/` (OpenCode), `.cursor/commands/` (Cursor),\n\
         `.github/extensions/forge-anything/` (Copilot CLI), and\n\
         `commands/rendered.json` (Pi, Hermes, Copilot CLI at runtime).\n\
         - `agents/` in every harness's native form too: `.claude/agents/`,\n\
         `.cursor/agents/`, `.opencode/agents/`, `.codex/agents/`,\n\
         `.pi/agents/`, `.github/agents/`, `.agents/agents/` (Antigravity\n\
         workspace scope), so any harness can delegate to the agents\n\
         directly instead of only through commands.\n\
         - `.mcp.json`, `mcp.json`, `.cursor/mcp.json`,\n\
         `.codex/config.toml`, `.opencode/opencode.json` - the `forge` MCP\n\
         server in each harness's project config form. These call bare\n\
         `forge`, so run the Forge Anything `install.sh` first.\n\
         - `docs/` - specs, plans, reports, templates, design, and\n\
         `docs/departments/` (one folder per department, with its audit\n\
         template).\n\
         - `AGENTS.md` - the operating rules. `WORKFLOW.md` - the workflow.\n\
         - `skills.json` - the manifest of the skills in this repo.\n\
         \n\
         Any agent or host reads `skills/` and `agents/` straight from this\n\
         folder. Commands and agents ship in each harness's native form; the\n\
         renders come from `scripts/sync-commands.py` and\n\
         `scripts/sync-agents.py` in the Forge Anything repo.\n\
         \n\
         ## Working here\n\
         \n\
         Read `AGENTS.md` first. Turn intent into a plan, then into work in\n\
         `docs/`. Verify before claiming anything is done.\n\
         \n\
         Copyright 2026 Galyarder Labs. Forge Anything.\n"
    )
}

/// The generated README for one department folder.
fn department_readme(department: &str) -> String {
    format!(
        "# Department: {department}\n\
         This directory contains persistent reports and strategic memory for the {department} department.\n\
         ---\n\
         Copyright 2026 Galyarder Labs. Forge Anything.\n"
    )
}

/// The generated `skills.json`: skill name -> `skills/<name>/SKILL.md`.
fn skills_manifest() -> String {
    let mut out = String::from("{\n");
    let mut first = true;
    for skill in curated::CURATED_SKILLS {
        if !first {
            out.push_str(",\n");
        }
        first = false;
        out.push_str(&format!("  \"{skill}\": \"skills/{skill}/SKILL.md\""));
    }
    out.push_str("\n}\n");
    out
}

/// Sensible default `.gitignore` for a scaffolded project.
const GITIGNORE: &str = "node_modules/\ntarget/\n.DS_Store\n*.log\n.env\n";

/// Copy one file, creating parent directories. Counts it in the summary.
fn copy_file(src: PathBuf, dst: PathBuf, s: &mut Summary) -> Result<(), String> {
    if let Some(parent) = dst.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("cannot create '{}': {e}", parent.display()))?;
    }
    fs::copy(&src, &dst).map_err(|e| {
        format!(
            "cannot copy '{}' -> '{}': {e}",
            src.display(),
            dst.display()
        )
    })?;
    s.note_file();
    Ok(())
}

/// Write one generated file, creating parent directories.
fn write_file(dst: PathBuf, contents: &str, s: &mut Summary) -> Result<(), String> {
    if let Some(parent) = dst.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("cannot create '{}': {e}", parent.display()))?;
    }
    fs::write(&dst, contents).map_err(|e| format!("cannot write '{}': {e}", dst.display()))?;
    s.note_file();
    Ok(())
}

/// Copy a directory tree (files only, following symlinks), with a depth cap
/// so a symlink loop cannot recurse forever.
fn copy_dir(src: &Path, dst: &Path, s: &mut Summary) -> Result<(), String> {
    copy_dir_depth(src, dst, s, 0)
}

fn copy_dir_depth(src: &Path, dst: &Path, s: &mut Summary, depth: usize) -> Result<(), String> {
    if depth > 12 {
        return Err(format!("directory tree too deep at '{}'", src.display()));
    }
    fs::create_dir_all(dst).map_err(|e| format!("cannot create '{}': {e}", dst.display()))?;
    for entry in read_dir_sorted(src)? {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().into_owned();
        let target = dst.join(&name);
        if path.is_dir() {
            copy_dir_depth(&path, &target, s, depth + 1)?;
        } else if path.is_file() {
            copy_file(path, target, s)?;
        }
        // Anything else (sockets, devices) is skipped deliberately.
    }
    Ok(())
}

/// Directory entries in sorted order, so the scaffold is deterministic.
fn read_dir_sorted(dir: &Path) -> Result<Vec<fs::DirEntry>, String> {
    let mut entries: Vec<fs::DirEntry> = fs::read_dir(dir)
        .map_err(|e| format!("cannot read '{}': {e}", dir.display()))?
        .collect::<Result<_, _>>()
        .map_err(|e| format!("cannot read '{}': {e}", dir.display()))?;
    entries.sort_by_key(|e| e.file_name());
    Ok(entries)
}
