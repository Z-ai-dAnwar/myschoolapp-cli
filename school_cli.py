#!/usr/bin/env python3
"""Thin CLI over myschoolapp-mcp's tool functions, so Claude can call them via Bash
instead of loading 32 MCP tool schemas into every session.

Usage:
  school list                         # tool names + one-line docs
  school <tool> ['{"arg": "value"}']  # run a tool, print JSON
"""
import asyncio, inspect, json, os, sys
from pathlib import Path

os.chdir(Path(__file__).parent)          # so .env is found
from dotenv import load_dotenv
load_dotenv()
from myschoolapp_mcp import server

BLOCKED = {"cookie_refresh"}             # never start a password login from here


# ---------------------------------------------------------------------------
# Class pages: bulletin board, topics, downloads (not covered upstream).
# Endpoints found by probing the US deployment on 2026-10-13. All GET.
# ---------------------------------------------------------------------------
import html as _html, re as _re

_LIST_Q = "?format=json&editMode=false&active=true&future=false&expired=false&contextLabelId=2"
# Bulletin-board module type -> list endpoint (per section)
_MODULES = {
    250: ("Text", "/api/text/forsection/{sid}/" + _LIST_Q),
    2: ("Links", "/api/link/forsection/{sid}/" + _LIST_Q),
    3: ("Downloads", "/api/download/forsection/{sid}/" + _LIST_Q),
    10: ("Announcements", "/api/announcement/forsection/{sid}/" + _LIST_Q),
    78: ("Syllabus", "/api/syllabus/forsection/{sid}/" + _LIST_Q),
    80: ("Expectations", "/api/expectation/forsection/{sid}/" + _LIST_Q),
    5: ("Events", "/api/event/forsection/{sid}/" + _LIST_Q),
    31: ("Photos", "/api/media/sectionmediaget/{sid}/" + _LIST_Q + "&contentId=31"),
}
_SKIP = {408}   # built-in widget on every class board; no list endpoint found, carries no posted content

def _get(path):
    r = server.api_request("GET", path)
    if r.get("status") != 200:
        return {"error": r.get("status"), "path": path.split("?")[0]}
    return r.get("body")

def _text(h):
    if not h:
        return ""
    h = _re.sub(r"(?i)<br\s*/?>|</(div|p|li|h\d)>", "\n", h)
    t = _html.unescape(_re.sub(r"<[^>]+>", "", h))
    return _re.sub(r"\n\s*\n+", "\n", t).strip()

def _clean(items):
    out = []
    for it in items if isinstance(items, list) else []:
        row = {}
        for k in ("Description", "Headline", "Name", "AlbumName", "ShortDescription"):
            if it.get(k):
                row["title"] = _text(it[k]); break
        body = it.get("LongText") or it.get("LongDescription") or it.get("BriefDescription")
        if body:
            row["text"] = _text(body)
        for k in ("Url", "DownloadUrl", "FileName", "FriendlyFileName", "PublishDate", "ExpireDate"):
            if it.get(k):
                row[k.lower()] = it[k]
        if it.get("FilePath") and it.get("FileName") and not it.get("DownloadUrl") and "thumb_" not in it["FileName"]:
            row["downloadurl"] = it["FilePath"] + it["FileName"]
        if "thumb_" in (it.get("FileName") or "") and len(row) <= 1:
            continue   # topic cover image
        out.append(row)
    return out

def _sections(section_id=None):
    cls = server.classes()
    rows = cls.get("body", []) if isinstance(cls, dict) else []
    if section_id:
        rows = [r for r in rows if str(r["section_id"]) == str(section_id) or str(section_id).lower() in r["class"].lower()]
    return rows

def class_list():
    """List classes with section ids and teachers (use the id or part of the name below)."""
    return [{"section_id": r["section_id"], "class": r["class"], "teacher": r["teacher"]} for r in _sections()]

def bulletin_board(section=None):
    """Read a class's bulletin board (text, links, downloads, announcements). section = id or name fragment; omit for all classes."""
    out = []
    for r in _sections(section):
        sid = r["lead_section_id"]
        layout = _get(f"/api/datadirect/BulletinBoardContentGet/?format=json&sectionId={sid}&associationId=1&pendingInd=false")
        types = [c["ContentId"] for c in layout] if isinstance(layout, list) else []
        mods = {}
        for t in dict.fromkeys(types):
            if t in _SKIP:
                continue
            if t in _MODULES:
                name, path = _MODULES[t]
                mods[name] = _clean(_get(path.format(sid=sid)))
            else:
                mods[f"type_{t}"] = "module type not supported yet"
        out.append({"class": r["class"], "section_id": sid, "modules": mods})
    return out

def topics(section=None):
    """List a class's topics (id + index id needed for topic_detail). section = id or name fragment; omit for all."""
    out = []
    for r in _sections(section):
        sid = r["lead_section_id"]
        ts = _get(f"/api/datadirect/sectiontopicsget/{sid}/?format=json&active=true&future=false&expired=false&sharedTopics=false")
        out.append({"class": r["class"], "topics": [
            {"topic_id": t["TopicID"], "topic_index_id": t["TopicIndexID"], "name": t["Name"],
             "description": _text(t.get("Description")), "published": t.get("PublishDate")}
            for t in (ts if isinstance(ts, list) else [])]})
    return out

def topic_detail(topic_id, topic_index_id):
    """Read everything inside one topic (text, links, files)."""
    items = _get(f"/api/datadirect/topiccontentget/{topic_id}/?format=json&index_id={topic_index_id}&id={topic_index_id}")
    return _clean(items)

def download(path, out_dir=".", name=None):
    """Save a file from the school site (a downloadurl like /ftpimages/...) into out_dir. Returns the saved path."""
    from pathlib import Path as _P
    c = server._get_client()
    resp = c._client.get(c._resolve_path(path))   # host-pinned client from upstream
    resp.raise_for_status()
    dest = _P(out_dir).expanduser() / (name or _P(path.split("?")[0]).name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return {"saved": str(dest), "bytes": len(resp.content)}

def read_assignment(assignment_index_id):
    """Open an assignment: description, links, and every attached file, downloaded to
    ~/.cache/school-portal/<id>/ with its text extracted (PDF via pdftotext, docx via textutil)."""
    import shutil, subprocess
    from pathlib import Path as _P
    from urllib.parse import urlparse
    d = server.assignment_detail(assignment_index_id).get("assignment", {})
    cache = _P("~/.cache/school-portal").expanduser() / str(assignment_index_id)
    files = []
    for f in d.get("resources", {}).get("downloads", []):
        path = urlparse(f["url"]).path
        saved = download(path, str(cache), f.get("name"))["saved"]
        text = None
        if saved.lower().endswith(".pdf") and shutil.which("pdftotext"):
            text = subprocess.run(["pdftotext", "-layout", saved, "-"], capture_output=True, text=True).stdout
        elif saved.lower().endswith((".docx", ".doc", ".rtf", ".txt")):
            text = subprocess.run(["textutil", "-convert", "txt", "-stdout", saved], capture_output=True, text=True).stdout
        files.append({"name": f.get("name"), "saved": saved, "text": (text or "").strip() or None})
    return {"title": d.get("title"), "class": d.get("class"), "due": d.get("due"), "status": d.get("status"),
            "description": d.get("description"), "links": d.get("resources", {}).get("links", []), "files": files}

# ---------------------------------------------------------------------------
# Durable login: a dedicated browser profile the user signs into ONCE by hand.
# When the API cookie dies, `refresh` reopens that profile headless; the saved
# Blackbaud ID / Microsoft "remember me" session mints a fresh cookie. No password
# is stored or typed by this tool.
# ---------------------------------------------------------------------------
import glob as _glob, time as _time

_AUTH_DIR = Path("~/.myschoolapp-mcp").expanduser()
_PROFILE = _AUTH_DIR / "profile"
_COOKIE = _AUTH_DIR / "cookie.txt"

def _portal():
    return f"https://{os.environ['MSA_SUBDOMAIN']}.myschoolapp.com"

def _browser_exe():
    if os.environ.get("MSA_BROWSER"):
        return os.environ["MSA_BROWSER"]
    hits = sorted(_glob.glob(os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*")))
    return hits[-1] if hits else None

def _harvest(headless, wait_s):
    from playwright.sync_api import sync_playwright
    _AUTH_DIR.mkdir(mode=0o700, exist_ok=True)
    _PROFILE.mkdir(mode=0o700, exist_ok=True)
    kw = {"headless": headless}
    exe = _browser_exe()
    if exe:
        kw["executable_path"] = exe
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(_PROFILE), **kw)
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(_portal() + "/app/student", timeout=60000)
        deadline = _time.time() + wait_s
        ok = False
        clicked = False
        probe = (_portal() + "/api/user/profiletabs?showuserid="
                 + os.environ.get("MSA_STUDENT_ID", "") + "&personaId=2")
        while _time.time() < deadline:
            _time.sleep(2)
            # Headless refresh: "Remember me" pre-fills the username, so clicking Next
            # hands off to the school's Microsoft SSO, which signs in from its own saved
            # session. Never fills a password.
            if headless and not clicked:
                try:
                    user = pg.query_selector("#Username")
                    nxt = pg.query_selector("#nextBtn")
                    if user and nxt and user.input_value() and nxt.is_visible():
                        nxt.click()
                        clicked = True
                except Exception:
                    pass
            if "t" in {c["name"] for c in ctx.cookies(_portal())}:
                try:
                    if ctx.request.get(probe).status == 200:
                        _time.sleep(2)
                        ok = True
                        break
                except Exception:
                    pass
        cookies = ctx.cookies(_portal())
        ctx.close()
    if not ok:
        return False
    header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    fd = os.open(_COOKIE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(header)
    server._drop_client()
    return True

def login():
    """Open a visible browser window. Sign in yourself (tick Remember me / Stay signed in). Saves a fresh cookie when done. Needed once, then only if refresh stops working."""
    ok = _harvest(headless=False, wait_s=300)
    return {"ok": ok, "next": "run `school whoami`" if ok else "login window timed out after 5 minutes"}

def refresh():
    """Get a fresh cookie invisibly from the saved login. Runs automatically when a command hits an expired session."""
    ok = _harvest(headless=True, wait_s=45)
    return {"ok": ok, "next": None if ok else "saved login expired; run `school login` and sign in again"}

def _expired(res):
    return isinstance(res, dict) and (res.get("auth_expired") or res.get("status") == 403)

_STATUS = {"todo": -1, "to do": -1, "in progress": 0, "inprogress": 0, "completed": 1, "done": 1, "complete": 1}

def mark(assignment_index_id, status="completed"):
    """The ONE write command: set your own Assignment Center status (todo / in progress / completed). Changes nothing else."""
    code = _STATUS.get(str(status).lower().strip())
    if code is None:
        return {"error": f"status must be one of: todo, in progress, completed (got {status!r})"}
    c = server._get_client()
    tok = c.request("GET", "/api/security/csrftoken").get("body")
    token = tok.get("TokenId") if isinstance(tok, dict) else tok
    r = c.request("POST", "/api/assignment2/assignmentstatusupdate",
                  json_body={"assignmentIndexId": int(assignment_index_id), "assignmentStatus": code},
                  extra_headers={"RequestVerificationToken": str(token)})
    after = server.assignment_detail(assignment_index_id).get("assignment", {})
    return {"http_status": r.get("status"), "title": _html.unescape(_html.unescape(after.get("title") or "")), "status_now": after.get("status")}

EXTRA = {f.__name__: f for f in (class_list, bulletin_board, topics, topic_detail, download, read_assignment, login, refresh, mark)}

def tools():
    out = {}
    for name, fn in vars(server).items():
        if name.startswith("_") or not inspect.isfunction(fn) or fn.__module__ != server.__name__:
            continue
        if name in BLOCKED or name == "main":
            continue
        out[name] = fn
    out.update(EXTRA)
    return out

def main():
    t = tools()
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "list"):
        for n, fn in sorted(t.items()):
            doc = (inspect.getdoc(fn) or "").splitlines()
            print(f"{n:28} {doc[0] if doc else ''}")
        return
    name = sys.argv[1]
    if name not in t:
        sys.exit(f"unknown or blocked tool: {name}. Run `school list`.")
    kwargs = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    def run():
        r = t[name](**kwargs)
        return asyncio.run(r) if inspect.isawaitable(r) else r
    try:
        res = run()
    except RuntimeError as e:          # no cookie file yet
        res = {"auth_expired": True, "error": str(e).splitlines()[0]}
    if name not in ("login", "refresh") and _expired(res) and _PROFILE.exists():
        if refresh()["ok"]:
            res = run()
        else:
            res = {"auth_expired": True, "next": "saved login expired; run `school login`"}
    print(json.dumps(res, indent=2, default=str))

if __name__ == "__main__":
    main()
