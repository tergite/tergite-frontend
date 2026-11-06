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
"""Replaces `ui/dist` with a page that sends the browser to the Vite dev server

Run from the repository root: `python -m dev.stub_dashboard`. `npm run dev` runs it so that MSS's
`/ui` never serves a stale build; a real build is made again with `npm run build`.
"""

import shutil
from pathlib import Path

DIST_DIR = Path(__file__).parents[1] / "ui" / "dist"
VITE_PORT = 5173
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
    """Empties `ui/dist` and leaves in it only the page that redirects to the Vite dev server"""
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    DIST_DIR.mkdir(parents=True)
    (DIST_DIR / "index.html").write_text(REDIRECT_PAGE)


if __name__ == "__main__":
    main()
