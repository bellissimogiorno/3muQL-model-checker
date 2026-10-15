# GitHub setup and online explorer

Version **0.7.1** includes everything needed to serve the model checker from
GitHub Pages. Visitors use the browser; no Python installation or solver server
is required. Python executes in a Web Worker through the pinned Pyodide runtime.
The built-in solver is the default; MiniSat is an optional additional download.

The target repository is
[`bellissimogiorno/3muQL-model-checker`](https://github.com/bellissimogiorno/3muQL-model-checker)
and its Pages address is
[`https://bellissimogiorno.github.io/3muQL-model-checker/`](https://bellissimogiorno.github.io/3muQL-model-checker/).
Unpacking this release does not update either one. The steps below publish it.

## Update the repository

The source archive expands into **`3muql-explorer/`**. Put its **contents** at
the Git repository root: `README.md`, `VERSION`, `pyproject.toml`, `index.html`,
`.nojekyll`, `.github/`, `site/`, `muql/`, and the other supplied directories must
be alongside one another. Do not put the handover directory or another
`3muql-explorer/` wrapper at the repository root.

For the existing repository, first clone it or use your existing clean
checkout:

```sh
git clone https://github.com/bellissimogiorno/3muQL-model-checker.git
cd 3muQL-model-checker
git switch main
```

Copy the extracted source directory's contents into that checkout, including
names beginning with a dot. Preserve the checkout's `.git` directory. Then run:

```sh
python tools/check_version.py
python tools/build_release.py --check
git status --short
git diff --stat
git add .
git commit -m "Release 3muQL Explorer 0.7.1: canonical command and verified fixes"
git push origin main
```

Review the changes before committing. If using GitHub's upload interface,
include `.github/` and `.nojekyll` too; some file managers hide them. The
prebuilt `site/` and `muql/_site.zip` are intentionally tracked release files,
even though temporary `dist/` products and virtual environments are excluded.

For a new empty repository instead, initialize the extracted source with
`git init -b main`, add and commit the files, add your new repository URL with
`git remote add origin URL`, then use `git push -u origin main`. Do not initialize
an unrelated history when updating the existing repository.

## Recommended: build and deploy with Actions

1. Open **Settings → Pages → Build and deployment → Source** and select
   **GitHub Actions**.
2. Open **Actions → Deploy explorer → Run workflow**, choose `main`, and run
   it. Later relevant pushes to `main` trigger it automatically.
3. Wait for the build, validation, and deployment jobs to succeed. Open the
   deployment URL shown by the workflow or in **Settings → Pages**.

This workflow builds the application directly into the artifact published at
the Pages root. Opening the existing Pages URL therefore displays the checker,
without a README page or an intermediate navigation choice. The build checks
release consistency, the engine, and browser behavior. Real Chromium/Pyodide
checks run under a project URL prefix and cover both the built-in and optional
native solver before deployment is allowed. Browser diagnostics are retained
as an Actions artifact. Only the deployment job requests Pages and
identity-token write permissions.

The real-browser gate remains required even when local browser validation
cannot run. Consult [release validation](validation.md) for the actual evidence
from this release; a workflow definition is not itself a successful deployment.
Repository permissions and GitHub's Pages availability still apply.

## Alternative: deploy the supplied files from a branch

For a repository already configured to publish a branch:

1. Select **Settings → Pages → Build and deployment → Source → Deploy from a
   branch**.
2. Select **main** and **/ (root)**, then save.
3. Wait for GitHub's Pages deployment and open the existing Pages URL.

The root `index.html` automatically forwards to `./site/`, where the complete
interactive application is already built. A visible link also permits manual
navigation. The final URL in this mode ends in `/3muQL-model-checker/site/`.
The root `.nojekyll` preserves the static files without a Jekyll build. Do not
select `/docs`: that is documentation, not the application.

This route publishes the checked-in snapshot; it does not run the custom
**Deploy explorer** browser-validation gate before publishing. Regenerate the
snapshot after source changes and run the available tests before committing.
Use the Actions route when you want deployment conditional on those checks.

If a published page still displays a README, check the selected Pages source
and the most recent successful deployment. Make sure `index.html` and `site/`
are present at the published root and are from 0.7.1. A README landing page is
consistent with a different publication source; this package does not claim to
have inspected your live repository settings.

## Local use and release updates

From the extracted source, or after installing the supplied wheel:

```sh
python -m muql serve --port 0 --open
```

The launcher prints a loopback address and stops with Ctrl+C. The installed
short form is `3muql serve --port 0 --open`; `muql` remains a compatibility
alias. The browser's default first load needs internet access for Pyodide; command-line checks are fully offline.
For source development, `bash serve.sh` rebuilds the site before serving it.

`VERSION`, `[project].version` in `pyproject.toml`, and `muql.__version__` must
agree. After edits, regenerate and check the distributed snapshots:

```sh
python tools/build_release.py --prepare-only
python tools/build_release.py --check
```

To build all four release products under `dist/releases/`, run
`python tools/build_release.py`; this additionally requires `setuptools>=61`
and `wheel` in the active Python environment. See [CONTRIBUTING.md](../CONTRIBUTING.md)
for validation and [the browser guide](browser.md) for runtime mirroring,
offline deployment, data handling, and the user workflow.

## Platform references

- [GitHub: configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [GitHub: custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
