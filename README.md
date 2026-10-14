# myschoolapp-cli

A command-line tool for Blackbaud K-12 school portals (`<school>.myschoolapp.com`). It reads your assignments and their attached files, grades, schedule, class bulletin boards, and topics from the terminal. It's built so an AI agent (or you) can run one command when it needs school info, instead of keeping a server plugged in all the time.

Read-only by default. It only talks to your school's own host.

Built on [6a6179/myschoolapp-mcp](https://github.com/6a6179/myschoolapp-mcp) (MIT). That project's original README, which covers running it as an MCP server, is in [`UPSTREAM-README.md`](UPSTREAM-README.md). Changes from upstream are listed in [`FORK.md`](FORK.md).

## Setup

```bash
git clone https://github.com/Z-ai-dAnwar/myschoolapp-cli.git
cd myschoolapp-cli
python3 -m venv .venv
.venv/bin/pip install -e .
```

Put a `school` command on your PATH:

```bash
printf '#!/bin/sh\nexec "%s/.venv/bin/python" "%s/school_cli.py" "$@"\n' "$PWD" "$PWD" > ~/.local/bin/school
chmod +x ~/.local/bin/school
```

Create `.env` (`chmod 600 .env`):

```
MSA_SUBDOMAIN=<the part before .myschoolapp.com>
MSA_STUDENT_ID=<your numeric user id>
MSA_TIMEZONE=America/New_York
```

You can find your user id in DevTools > Network on the portal. It's the number in `large_user_<id>_...jpg` or `showuserid=<id>`.

### Cookie

Log in to the portal in your browser. Open DevTools > Network, click any `/api/` request, and copy the value of the `cookie:` request header. Then:

```bash
mkdir -p ~/.myschoolapp-mcp && chmod 700 ~/.myschoolapp-mcp
pbpaste > ~/.myschoolapp-mcp/cookie.txt && chmod 600 ~/.myschoolapp-mcp/cookie.txt   # macOS
```

Don't paste the cookie into a chat or commit it. It logs in as you. It expires every few weeks; when commands start failing with an auth error, copy a fresh one.

## Commands

```bash
school list                                   # every command
school whoami                                 # check the cookie works
school assignments                            # everything due, grouped (today, tomorrow, this week...)
school missing_assignments
school read_assignment '{"assignment_index_id": 123}'   # description + attachments, text extracted
school gradebook
school schedule
school class_list                             # classes, section ids, teachers
school bulletin_board '{"section": "english"}'          # id or part of the class name
school topics '{"section": "physics"}'
school topic_detail '{"topic_id": 1, "topic_index_id": 2}'
school download '{"path": "/ftpimages/...", "out_dir": "~/Downloads", "name": "file.pdf"}'
```

Arguments are a JSON object. `read_assignment` saves attachments to `~/.cache/school-portal/<id>/`.

## Safety

- Every command only reads. `cookie_refresh`, which starts a password login, is blocked in the CLI. Writes through `api_request` stay off unless you set `MSA_ALLOW_WRITES`.
- Requests are pinned to your school's HTTPS host, redirects included.
- Don't run `scripts/probe_api.py`. It's an upstream developer tool that dumps raw API responses and cookies to disk.
- The endpoints are private and were reverse-engineered, so they can break whenever Blackbaud changes the site.
- This is unofficial and not affiliated with Blackbaud. Check your school's technology policy before using it.

## License

MIT, same as upstream. See [`LICENSE`](LICENSE).
