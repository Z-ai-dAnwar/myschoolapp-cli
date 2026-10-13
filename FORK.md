# About this copy

Private copy of [6a6179/myschoolapp-mcp](https://github.com/6a6179/myschoolapp-mcp) (MIT), based on upstream commit `598f943`, which was security-reviewed on 2026-10-13. The original copyright and LICENSE are kept.

## Changes from upstream
- `school_cli.py`: a thin CLI over the server's tool functions (`school list`, `school <tool> '{json args}'`), so an agent can call tools from the shell instead of loading 32 MCP tool schemas into every session. `cookie_refresh` is blocked in the CLI.

## Safe config
`.env` holds only `MSA_SUBDOMAIN`, `MSA_STUDENT_ID`, and `MSA_TIMEZONE`. No password, no `MSA_AUTO_REFRESH`, no `MSA_ALLOW_WRITES`. The cookie goes in `~/.myschoolapp-mcp/cookie.txt` (chmod 600). Do not run `scripts/probe_api.py`.

## Upstream
`git fetch upstream` to see new upstream work. Review every upstream change before merging. Changes worth sharing go back as pull requests to the original repo.
