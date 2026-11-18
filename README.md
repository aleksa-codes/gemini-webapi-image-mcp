# Gemini Image MCP

Generate and edit images with Gemini Nano Banana through MCP. Uses the Gemini website with your Google session, not the official API. No API key required.

## Authentication

The server needs a signed-in Google session. **You usually do not need to copy or configure cookies on your own computer.**

| Where the MCP server runs                                                 | What to do                                                                                                                                          |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| On your computer, with a readable Chrome profile                          | Sign in at [gemini.google.com](https://gemini.google.com) in Chrome. Cookies are read automatically. Leave `GEMINI_PSID` and `GEMINI_PSIDTS` unset. |
| On a VPS, in a container, or without access to a signed-in Chrome profile | Provide cookies manually using the [fallback below](#manual-cookies).                                                                               |

What matters is where the **MCP process** runs, not where you open your editor. If automatic Chrome access fails, manual cookies are also an option.

## Connect

Requires [uv](https://docs.astral.sh/uv/), Python 3.11 or later, and GitHub
access to this repository.

### OpenCode

Register for all projects (omit `--global` for this project only):

```sh
opencode mcp add gemini-image --global -- uvx --from git+https://github.com/aleksa-codes/gemini-webapi-image-mcp.git gemini-image-mcp
```

No clone or cookie settings are needed with automatic Chrome authentication. Other MCP clients can use the same `uvx` command and arguments as a local **stdio** server.

<details>
<summary>Run from a local checkout</summary>

From the repository directory:

```sh
uv sync
uv run gemini-image-mcp
```

In an MCP client, use `uv --directory /absolute/path/to/gemini-webapi-image-mcp run gemini-image-mcp`.

</details>

## Manual cookies

**Skip this section if automatic Chrome authentication works.**

1. Sign in at `gemini.google.com` in Chrome.
2. Open DevTools, then **Application > Cookies > https://gemini.google.com**.
3. Copy `__Secure-1PSID` and, preferably, `__Secure-1PSIDTS`.
4. Pass them to the MCP process as `GEMINI_PSID` and `GEMINI_PSIDTS`. The second value is optional but recommended.

For a server launched from your shell:

```sh
export GEMINI_PSID="your __Secure-1PSID value"
export GEMINI_PSIDTS="your __Secure-1PSIDTS value"
```

For an editor-managed server, use the client's environment settings. In OpenCode, add an `environment` object to the `gemini-image` entry with `GEMINI_PSID` and `GEMINI_PSIDTS`, preferably referencing secrets as `{env:GEMINI_PSID}` and `{env:GEMINI_PSIDTS}`. The referenced variables must be available to OpenCode itself.

Manual values take priority over Chrome. To return to automatic authentication, remove them. Cookies are session credentials: never commit or share them. If they expire, replace the values supplied to the MCP process and reconnect the server.

## Tools

| Tool             | Use                                                                           |
| ---------------- | ----------------------------------------------------------------------------- |
| `generate_image` | Create an image, or refine a previous generation using its `conversation_id`. |
| `edit_image`     | Edit local images supplied through `paths`. At least one path is required.    |
| `status`         | Check authentication without disturbing the shared session.                   |
| `reset`          | Re-initialise the client and re-read cookies.                                 |

Both image tools accept `aspect_ratio`, `output_dir`, and `temporary` and return JSON with saved image paths and a `conversation_id`.

- **Refinements:** pass the returned `conversation_id` and an editing prompt to `generate_image`. Prefer this over re-uploading the saved image. Use `edit_image` for external images or when the original conversation is unavailable.
- **Output:** images save to `~/Pictures/gemini/`. Downloads request full-size images by default; use `output_dir` to save elsewhere.
- **History:** `temporary=True` by default. Use `temporary=False` only when you want the conversation saved to Gemini history.

## Optional settings

No environment variables are required when automatic Chrome authentication works. These only override defaults.

| Variable                  | Default              | Purpose                                                              |
| ------------------------- | -------------------- | -------------------------------------------------------------------- |
| `GEMINI_OUTPUT_DIR`       | `~/Pictures/gemini/` | Default save directory. Per-call `output_dir` takes priority.        |
| `GEMINI_ACCOUNT_INDEX`    | `0`                  | Google account index when several accounts are signed in.            |
| `GEMINI_LANGUAGE`         | `en`                 | Language hint for image requests.                                    |
| `GEMINI_SKIP_2X`          | `0`                  | Set `1` to download previews instead of requesting full-size images. |
| `GEMINI_GEN_TIMEOUT`      | `600`                | Generation timeout in seconds.                                       |
| `GEMINI_DOWNLOAD_TIMEOUT` | `60`                 | Per-image download timeout in seconds.                               |
| `CHROME_COOKIE_FILE`      | Chrome default       | Custom cookie file for automatic authentication.                     |

<details>
<summary>Debug settings</summary>

Leave these unset unless diagnosing a problem.

| Variable                | Default            | Purpose                                                                              |
| ----------------------- | ------------------ | ------------------------------------------------------------------------------------ |
| `GEMINI_IMAGE_MODEL_ID` | `56fdd199312815e2` | Override the internal fast-image model ID if Google rotates it.                      |
| `GEMINI_NO_REMAP`       | `0`                | Set `1` to disable the model-ID override.                                            |
| `GEMINI_NO_BODY`        | `0`                | Set `1` to skip browser body parameters, keeping header and temporary-mode patching. |
| `GEMINI_DEBUG_TIMING`   | `0`                | Set `1` to log stage timings.                                                        |

</details>

## Troubleshooting

- **Authentication fails:** call `status`. With automatic authentication, sign in again in Chrome and call `reset`. With manual authentication, replace the supplied cookie values and reconnect the server.
- **"Are you signed in?" or error 1096:** update older server versions. Chrome cookie selection now accepts only `.google.com`, excluding country domains such as `.google.com.bd`. This fix does not change manual cookies or resolve every account-side failure.
- **Generation is throttled or blocked:** wait before retrying. Fresh cookies do not necessarily fix account or regional restrictions.

## For agents

See [AGENTS.md](AGENTS.md) for contributor checks. To use the server,
copy the optional [skill directory](skill/) into your client's skills
directory as `gemini-image`. Keep the bundled prompting reference with it.

## Credits

Image pipeline and prompting guide adapted from [aleksa-codes/gemini-webapi-mcp](https://github.com/aleksa-codes/gemini-webapi-mcp), a fork of [AndyShaman/gemini-webapi-mcp](https://github.com/AndyShaman/gemini-webapi-mcp). The request layer was rewritten for [HanaokaYuzu/Gemini-API](https://github.com/HanaokaYuzu/Gemini-API) 2.x.

## License

[AGPL-3.0-or-later](LICENSE)
