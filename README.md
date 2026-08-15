# skills

Private repo of Agent Skills and Claude Code plugins.

Not related to Rex. Nothing here carries Rex catalog metadata.

## Layout

```
skills/<name>/SKILL.md     one folder per skill, name matches the dir
plugins/<name>/            Claude Code plugin bundles
```

## Pulling from here

Install the local `git` MCP server, then in any Claude surface:

1. `git_sync` with `seanx10m/skills` - clones or updates the local checkout
2. `git_ls` to see what is in it
3. `git_read` to look at a `SKILL.md`
4. `git_export` a skill folder to `~/.claude/skills/<name>` to install it

Server source: `~/code/other/git-mcp/git_mcp.py`
