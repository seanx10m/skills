# skills

A private Claude Code **plugin marketplace**.

Not related to Rex. Nothing here carries Rex catalog metadata.

## Install

```
/plugin marketplace add seanx10m/skills
/plugin install personal-skills@skills
```

Both need a `gh`/git login that can see this private repo. It is owned by `seanx10m`, so if
another account is active you get `Repository not found` - GitHub returns the same 404 for
"private and invisible to you" as for "does not exist". Fix with `gh auth switch -u seanx10m`.

Update later with `/plugin update personal-skills`.

## Layout

```
.claude-plugin/marketplace.json      the marketplace index
plugins/<plugin>/
  .claude-plugin/plugin.json         plugin metadata
  skills/<name>/SKILL.md             one folder per skill
  hooks/hooks.json                   event handlers
```

## Plugins

### personal-skills

Nine skills: `bullet`, `define`, `session-state`, `dream-outcome`, `loop-pre-flight`,
`lorax`, `quiz-me`, `progress-hud`, `done-sound`.

Ships a `SessionStart` hook that checks at most once a day whether this repo has moved ahead
of what is installed, and if so says so. It exits 0 on every path - no network, no git, no
plugin root, all fine - so it can never block a session from starting.

## Scope

Plugins and marketplaces are a **Claude Code** feature. Claude Desktop chat and Cowork do not
read them. To pull these skills onto those surfaces, use the `git-mcp` local MCP server
(`~/code/other/git-mcp`), which exposes git and gh as tools and can copy a skill folder onto
disk.
