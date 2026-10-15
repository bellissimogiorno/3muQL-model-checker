# GitHub setup and the browser demo

## Upload the repository

The source archive expands into **`3muql-explorer/`**. That directory is the
repository root: it contains `README.md`, `VERSION`, `pyproject.toml`, the
`muql/` Python package, examples, tests, documentation, and reference reports.
Build products and virtual environments are excluded. The GitHub Actions test
workflow is included in `.github/workflows/tests.yml`.

Create an empty GitHub repository named `3muql-explorer`. Leave GitHub's options
to add a README, license, and gitignore unchecked, because these files are
already included. From the extracted directory, run the following commands,
replacing `YOUR-USERNAME` with your GitHub username or organization:

```sh
cd 3muql-explorer
python tools/check_version.py
python demo.py --search-only --brief
git init -b main
git add .
git commit -m "Release 3μQL Explorer 0.6.4"
git remote add origin https://github.com/YOUR-USERNAME/3muql-explorer.git
git push -u origin main
```

Use the contents of `3muql-explorer/` as the repository root, rather than
placing that directory inside another repository directory. `git add .`
includes the supplied GitHub Actions workflow and gitignore file. If uploading
through GitHub's web interface instead, include those files too; some file
managers conceal names beginning with a dot.

The CI workflow checks version agreement, runs the test suite and demonstration,
and tests the optional native SAT backend separately. Its configuration is
included; no repository has been created or pushed on your behalf.

`VERSION`, `[project].version` in `pyproject.toml`, and `muql.__version__` must
agree. Run `python tools/check_version.py` after a version change. The check
uses only the standard library and supports Python 3.10 and later.

## Publish the browser explorer

The interactive demo is implemented in `web/`, sharing the Python engine via
`muql/web.py`. It includes an example selector, theory editor, optional axiom
removal, property selection, bounded search and fixed-frame checking,
cancellation, counterexample tables, and replayable downloads.

After uploading the repository:

1. Choose **Settings → Pages → GitHub Actions**.
2. Run **Actions → Browser demo → Run workflow**.
3. Follow the deployment URL when the workflow succeeds.

The workflow builds the static site and tests it with the real Python runtime
in Chromium at a project path before publishing. Those browser checks must
pass; they were not run locally during release preparation because browser
binaries and runtime downloads were unavailable.

For a local preview, run:

```sh
bash serve.sh
```

The Bash launcher defaults to `python3`; use `bash serve.sh --python python`
if that is your Python 3.10+ command. The script builds
the site and serves it at `http://127.0.0.1:8000/`; press **Ctrl+C** to stop.
Add `--open` to open your browser or `--port 0` to choose a free port.
The site fetches a pinned Pyodide runtime on
first use. Python runs in a module worker, so a search does not block page
interaction. Stop terminates that worker; the next run starts a new one.
The built-in solver is the default, with MiniSat available as an optional
additional download. No Python server or solver service is required.

See [the browser guide](browser.md) for the user workflow, data handling,
solver choices, limitations, and details of the Pages deployment. The release
is ready to upload; no GitHub repository or live site has been created here.
