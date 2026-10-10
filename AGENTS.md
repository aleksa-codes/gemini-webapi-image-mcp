# AGENTS.md

## What is this

Image-only MCP server for Gemini (Nano Banana) via unofficial web-client cookies. Python, single package, no monorepo. Ported from `../gemini-webapi-mcp` (image pipeline only).

## Setup

```bash
uv sync                 # install deps (requires Python 3.10+)
uv run gemini-image-mcp # run the MCP server (stdio)
```

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run server | `uv run gemini-image-mcp` |
| Typecheck | `uv run --group dev pyright` (if configured) |

No tests, no linter, no CI.

## Architecture

All source lives in `src/gemini_webapi_image_mcp/`:

- `__init__.py` — entry point, calls `mcp.run()`
- `server.py` — tools (`generate_image`, `edit_image`, `status`, `reset`), client patching, cookie resolution

**Entry flow:** `gemini-image-mcp` CLI → `__init__.py:main()` → `FastMCP.run()` (stdio).

**Key internals (ported from the fork, keep in sync when it changes):**
- `_patch_client()` monkey-patches `GeminiClient` with browser request params and captures download tokens.
- `_fetch_download_url()` calls `c8o8Fe` RPC for 2x upscaled downloads.
- `_generate()` is the shared core; both image tools call it.
- Generations are serialized via `_image_lock`; hard timeout `GEMINI_GEN_TIMEOUT` (default 600s).

## Critical conventions

- **stdout = MCP protocol only.** All logging goes to stderr. Never print to stdout.
- **`temporary=True` is the default** on both image tools. Only set False when the user explicitly wants history.
- Cookie values are never logged (lengths only, in `status`).

## Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `GEMINI_PSID` / `GEMINI_PSIDTS` | Manual cookie override | auto from Chrome |
| `GEMINI_ACCOUNT_INDEX` | Google account index | `0` |
| `GEMINI_LANGUAGE` | Request language for image route | `en` |
| `GEMINI_GEN_TIMEOUT` | Generation hard cap (seconds) | `600` |
| `GEMINI_DOWNLOAD_TIMEOUT` | Image download timeout (seconds) | `60` |
| `GEMINI_SKIP_2X` | Set `1` to skip 2x upscale RPC | `0` |
| `GEMINI_NO_REMAP` | Set `1` to skip model-ID remap | `0` |
| `GEMINI_NO_BODY` | Set `1` to skip body-param injection (keeps header + temp). Diagnostic bisect only | `0` |
| `GEMINI_DEBUG_TIMING` | Set `1` to log per-stage wall-time | `0` |
| `GEMINI_IMAGE_MODEL_ID` | Override model ID for image requests | `56fdd199312815e2` |
| `GEMINI_OUTPUT_DIR` | Default directory for saved images | `~/Pictures/gemini/` |

## Dependencies

`gemini-webapi` (xob0t fork on GitHub, not PyPI), `mcp`, `browser-cookie3`, `orjson`, `curl-cffi`.

> Migrated to upstream `HanaokaYuzu/Gemini-API` 2.x (was xob0t fork). The 2.x request/response layers differ, so the port was rewritten, not copied: request patching kept (model header, body params, temp flag, file fix), response/token/c8o8Fe machinery dropped (native parsing + native full-size RPC instead), exceptions remapped.
>
> Verified on VPS: tools register, client init + patch apply cleanly, error mapping works. NOT verified: actual image bytes — this VPS account returns API error 1096 for ALL generation (even unpatched plain-text requests), so it's account-level, not code. Bisect (NO_REMAP, NO_BODY, fully native text call) proved the patch innocent. First real image test must happen where generation works.
>
> Do not switch back to xob0t without reason: its request shape is what the old code assumed; the current code targets 2.x.

## License

AGPL-3.0-or-later.
