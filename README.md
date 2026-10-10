# gemini-webapi-image-mcp

MCP server for Gemini **image generation and editing only**, via an unofficial web client (browser cookies). No API keys. Free.

> **Not the official Gemini API.** This talks to `gemini.google.com` the same way a logged-in browser does, using `__Secure-1PSID` / `__Secure-1PSIDTS` cookies. Google may rotate or invalidate cookies at any time; when calls start failing with auth errors, refresh the cookies (see below).

## Tools

| Tool | What |
|------|------|
| `generate_image` | New image from a text prompt (Nano Banana) |
| `edit_image` | Transform existing image(s) from a prompt |
| `status` | Validate cookies without disturbing the session |
| `reset` | Re-initialise the client with fresh cookies |

`generate_image` and `edit_image` default to `temporary=True` (nothing saved to Gemini history). Pass `temporary=False` to persist generations to the account. Both return JSON with saved paths plus `conversation_id` for iterative refinement ("make it more dramatic").

Images save to `~/Pictures/gemini/` by default (`GEMINI_OUTPUT_DIR` env var or per-call `output_dir` overrides). 2x upscaled downloads via `c8o8Fe` RPC unless `GEMINI_SKIP_2X=1`.

## Setup

```bash
uv sync
uv run gemini-image-mcp
```

## Connect

### OpenCode

Add to `opencode.json` (no clone needed; needs SSH access to the private repo):

```json
{
  "mcp": {
    "gemini-image": {
      "type": "local",
      "command": [
        "uvx",
        "--with",
        "gemini-webapi-image-mcp @ git+https://github.com/aleksa-codes/gemini-webapi-image-mcp.git",
        "gemini-image-mcp"
      ],
      "enabled": true,
      "environment": {
        "GEMINI_PSID": "paste-your-PSID",
        "GEMINI_PSIDTS": "paste-your-PSIDTS"
      }
    }
  }
}
```

### Claude Code / Claude Desktop

```bash
claude mcp add gemini-image -- uvx --with "gemini-webapi-image-mcp @ git+https://github.com/aleksa-codes/gemini-webapi-image-mcp.git" gemini-image-mcp -e GEMINI_PSID="..." -e GEMINI_PSIDTS="..."
```

## Cookies

No browser on the machine? Set env vars (this is the only auth path then):

```bash
export GEMINI_PSID="..."
export GEMINI_PSIDTS="..."   # optional but recommended
```

With a logged-in Chrome present, cookies are read automatically. Refresh flow when `status` reports expired: Chrome devtools → Application → Cookies → `https://gemini.google.com` → copy `__Secure-1PSID` and `__Secure-1PSIDTS` → update env → call `reset`. Takes about a minute.

## Credits

- Image pipeline, client patching, and cookie approach ported from [aleksa-codes/gemini-webapi-mcp](https://github.com/aleksa-codes/gemini-webapi-mcp) (fork of [AndyShaman/gemini-webapi-mcp](https://github.com/AndyShaman/gemini-webapi-mcp)).
- Web client library: [xob0t/Gemini-API](https://github.com/xob0t/Gemini-API) (`gemini-webapi`).
- Prompting guide adapted from the same fork.

## License

AGPL-3.0-or-later (same as the sources it ports). In plain terms:

- **Use it freely**, privately or commercially, modified or not. Running it for your own agents (even on a VPS) triggers no obligations.
- **If you share a modified version** (publish a fork, or run it as a service others use), you must publish your modified source under the same license.
- **You cannot** relicense it or derivatives as closed source.

Keeping this repo private and unmodified-in-spirit means the license stays out of your way.
