# Changes from upstream

Private copy of [6a6179/myschoolapp-mcp](https://github.com/6a6179/myschoolapp-mcp) (MIT), based on upstream commit `598f943`, which was security-reviewed on 2026-10-13. The original copyright and LICENSE are kept.

## Changes from upstream
- `school_cli.py`: a thin CLI over the server's tool functions (`school list`, `school <tool> '{json args}'`), so an agent can call tools from the shell instead of loading 32 MCP tool schemas into every session. `cookie_refresh` is blocked in the CLI.
- Class-page commands not in upstream (endpoints probed on the US deployment, 2026-10-13, all GET):
  - `class_list`: section ids, class names, teachers
  - `bulletin_board [section]`: text, links, downloads, announcements, syllabus, expectations, events, photos per class. `section` = id or a name fragment like "english". Module 408 is a built-in widget with no content and is skipped.
  - `topics [section]` and `topic_detail topic_id topic_index_id`: topic lists and everything inside one topic, including file `downloadurl`s
  - `download path [out_dir] [name]`: save a file through the host-pinned client
  - `login` / `refresh`: a dedicated browser profile the user signs into once. Expired sessions are refreshed headless from it and the command is retried automatically. No password stored. Replaces upstream's password-based `cookie_refresh`.
  - `mark assignment_index_id [status]`: the ONE write command. It sets your own Assignment Center status (todo / in progress / completed) via POST /api/assignment2/assignmentstatusupdate with a CSRF token. Verified 2026-10-13.
  - `read_assignment assignment_index_id`: description, links, and every attachment downloaded to `~/.cache/school-portal/<id>/` with text extracted

## Safe config
`.env` holds only `MSA_SUBDOMAIN`, `MSA_STUDENT_ID`, and `MSA_TIMEZONE`. No password, no `MSA_AUTO_REFRESH`, no `MSA_ALLOW_WRITES`. The cookie goes in `~/.myschoolapp-mcp/cookie.txt` (chmod 600). Do not run `scripts/probe_api.py`.

- `server.py` assignment_detail: when `Grade` is blank but `HasGrade` is set, fall back to `GradebookGrade` (seen on US, 2026-10-14).

## Upstream
`git fetch upstream` to see new upstream work. Review every upstream change before merging. Changes worth sharing go back as pull requests to the original repo.
