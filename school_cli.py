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

def tools():
    out = {}
    for name, fn in vars(server).items():
        if name.startswith("_") or not inspect.isfunction(fn) or fn.__module__ != server.__name__:
            continue
        if name in BLOCKED or name == "main":
            continue
        out[name] = fn
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
    res = t[name](**kwargs)
    if inspect.isawaitable(res):
        res = asyncio.run(res)
    print(json.dumps(res, indent=2, default=str))

if __name__ == "__main__":
    main()
