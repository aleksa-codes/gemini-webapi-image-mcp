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
| `GEMINI_DEBUG_TIMING` | Set `1` to log per-stage wall-time | `0` |
| `GEMINI_IMAGE_MODEL_ID` | Override model ID for image requests | `56fdd199312815e2` |
| `GEMINI_OUTPUT_DIR` | Default directory for saved images | `~/Pictures/gemini/` |

## Dependencies

`gemini-webapi` (xob0t fork on GitHub, not PyPI), `mcp`, `browser-cookie3`, `orjson`, `curl-cffi`.

> Evaluated switching to upstream `HanaokaYuzu/Gemini-API` 2.1.1: incompatible without a rewrite. It posts to `batchexecute` (request patches filter on `StreamGenerate`, so they'd silently die), has no `Model.from_name` / `parse_response_by_frame` / `_parse_generated_images` (patches would crash lifespan init), and uses different exceptions. Upstream is better long-term (native temp flag, native full-size, per-account model discovery) but adopting it needs a rewrite verified where image gen actually works. Do not retry blindly.

## License

AGPL-3.0-or-later.
