# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Replaces `ui/dist` with the pages MSS serves at `/ui` while the dashboard runs on Vite

Run from the repository root: `python -m dev.stub_dashboard`. `npm run dev` runs it, so that MSS's
`/ui` never serves a stale build; `npm run build` makes a real build again. It writes:

- `index.html`, which sends the browser to the same page on the Vite dev server
- `dev-login.html`, which logs in as any user in `ui/fixtures/users.json`, with no OAuth provider
"""

import html
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import settings
from dev.seed import FIXTURES_DIR
from libs.authlib.tokens import write_session_token

DIST_DIR = Path(__file__).parents[1] / "ui" / "dist"
VITE_PORT = 5173
# a week, so that a login lasts a working week of `npm run dev` without logging in again
SESSION_SECONDS = 7 * 24 * 3600
REDIRECT_PAGE = f"""<!doctype html>
<meta charset="utf-8" />
<title>Redirecting to the dev server</title>
<script>
  location.replace(
    `${{location.protocol}}//${{location.hostname}}:{VITE_PORT}${{location.pathname}}${{location.search}}${{location.hash}}`,
  );
</script>
"""


def main() -> None:
    """Empties `ui/dist`, then writes the redirect and dev login pages into it"""
    if settings.CONFIG.environment == "production":
        sys.exit(
            "dev.stub_dashboard: refusing to write login tokens for a production config"
        )
    users = json.loads((FIXTURES_DIR / "users.json").read_text())
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    DIST_DIR.mkdir(parents=True)
    (DIST_DIR / "index.html").write_text(REDIRECT_PAGE)
    (DIST_DIR / "dev-login.html").write_text(_get_login_page(users))


def _get_login_page(users: list[dict]) -> str:
    """The page whose buttons log in as each user, with a session cookie as MSS would set"""
    auth = settings.CONFIG.auth
    cookie_domain = f"; domain={auth.cookie_domain}" if auth.cookie_domain else ""
    buttons = "\n".join(_get_login_button(user) for user in users)
    return f"""<!doctype html>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Dev login</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem; }}
  button {{ display: block; width: 100%; text-align: left; padding: .75rem 1rem; margin: .5rem 0;
    font: inherit; border: 1px solid #ccc; border-radius: .5rem; background: none; cursor: pointer; }}
  button:hover {{ border-color: #666; }}
  small {{ color: #666; }}
</style>
<h1>Log in as</h1>
<p><small>Development only: the seeded users of <code>ui/fixtures/users.json</code>.</small></p>
<p id="error" role="alert" hidden style="color: #b00020"></p>
{buttons}
<script>
  const cookieName = {json.dumps(auth.cookie_name)};
  const cookieDomain = {json.dumps(auth.cookie_domain)};
  for (const button of document.querySelectorAll("button[data-token]")) {{
    button.addEventListener("click", () => {{
      const cookie = `${{cookieName}}=${{button.dataset.token}}`;
      document.cookie = `${{cookie}}; path=/; max-age={SESSION_SECONDS}; samesite=lax{cookie_domain}`;
      if (!document.cookie.split("; ").includes(cookie)) {{
        // browsers drop a cookie whose domain is not this page's host without saying so
        const error = document.getElementById("error");
        error.textContent = cookieDomain && cookieDomain !== location.hostname
          ? `The browser refused the login cookie: cookie_domain in [auth] of mss-config.toml is "${{cookieDomain}}", ` +
            `but this page is at "${{location.hostname}}", where the dashboard calls MSS. ` +
            `Set cookie_domain = "${{location.hostname}}" and restart npm run dev.`
          : `The browser refused the login cookie; a "${{cookieName}}" cookie MSS set itself may be in the way: ` +
            `clear this site's cookies and try again.`;
        error.hidden = false;
        return;
      }}
      location.assign(`${{location.protocol}}//${{location.hostname}}:{VITE_PORT}/ui/`);
    }});
  }}
</script>
"""


def _get_login_button(user: dict) -> str:
    """The button that logs in as the user"""
    token = write_session_token(
        SimpleNamespace(id=user["id"], roles=user["roles"]),
        settings.CONFIG.auth.jwt_secret,
        SESSION_SECONDS,
    )
    roles = ", ".join(user["roles"])
    return (
        f'<button data-token="{token}">{html.escape(user["email"])}'
        f"<br /><small>{html.escape(roles)}</small></button>"
    )


if __name__ == "__main__":
    main()
