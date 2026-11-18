# AGENTS.md

Python 3.11+ MCP stdio server for Gemini image generation and editing. Use uv
and the upstream HanaokaYuzu Gemini-API 2.x integration, not the xob0t fork.

- Install with `uv sync`. Run with `uv run gemini-image-mcp`.
- Run `uv run pyright`. No automated tests, lint, or format command is
  configured. Do not use live account credentials for routine verification.
- Keep stdout reserved for MCP protocol messages and log to stderr. Never
  log session cookie values. Keep exact `.google.com` filtering despite
  the browser cookie library's substring matching.
- Preserve request patching and generation serialization in
  `src/gemini_webapi_image_mcp/server.py`. Use upstream image parsing and
  full-size downloads; do not reintroduce the sister repo's manual token/RPC path.
- Keep both image tools temporary by default. Tool registration or a successful
  auth probe does not verify image bytes were saved. Error 1096 can occur even
  on unpatched requests, so isolate account issues before changing the patch.
