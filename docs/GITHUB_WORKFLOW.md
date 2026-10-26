# A reviewable GitHub history

LedgerX was developed locally before its first repository publication. Its initial import should
describe that fact. Subsequent commits and pull requests should record actual changes, with their
real creation dates and executed checks. No backdated commits, fictional reviews or invented
development incidents are part of this workflow.

The GitHub account supplied for publication is `anaselmadhi`, and the repository URL is
`https://github.com/anaselmadhi/LedgerX.git`. The initial publication is complete: local import
[`6b5a135`](https://github.com/anaselmadhi/LedgerX/commit/6b5a135) was merged with GitHub's starter
README in [`d65fb3c`](https://github.com/anaselmadhi/LedgerX/commit/d65fb3c), and the owner supplied
a successful push result. The owner subsequently supplied the successful Actions run #1 summary
for `d65fb3c`: both `verify` and `container-browser` passed. See the
[recorded CI evidence](../artifacts/ci/initial-run-summary.json). No pull request has been claimed
for this initial import.

## Initial import

Suggested title: `Import LedgerX financial demo developed locally`

Describe the existing modular monolith, immutable double-entry journal, auth/ownership, full
compensating refunds, reconciliation, React UI and reproducible tests. Include the honest evidence
snapshot from the engineering report. Review ignored and tracked artifacts before publishing.
Future changes belong in branches created from this imported state.

### First publication from the Mac

The initial import below has already been completed. Keep these instructions as a record of that
procedure; future changes need a new commit and push, not another repository initialization.

The GitHub repository already exists and may contain the README, gitignore or license selected
during repository creation. Keep those remote files; do not delete the repository or force-push over
its initial commit. The local project already contains a detailed README and ignore rules. During
the initial merge, keep the detailed local README and `.gitignore` if Git reports conflicts, while
preserving any separate license file from GitHub. Keep passwords and access tokens out of the chat,
remote URL and repository files.

From this directory, the initial local preparation is:

```bash
git init -b main
git add .github .gitignore .dockerignore .env.example app alembic frontend scripts tests docker \
  analysis docs output/pdf README.md INTERVIEW_NOTES.md pyproject.toml uv.lock alembic.ini \
  Dockerfile compose.yaml compose.share.yaml render.yaml
# Curated measured evidence; large/private runtime data and diagnostic logs stay excluded:
git add artifacts/README.md artifacts/benchmark.json artifacts/profiling.json artifacts/baseline \
  artifacts/figures artifacts/latency artifacts/releases artifacts/frontend-delivery.json
git diff --cached --stat
git diff --cached --check
```

Review the staged files before committing, especially recorded evidence. `.runtime` (database and
private backups), `.venv`, credentials, dependencies, logs and browser failure captures are ignored.
The initial import includes actual source and measurements; it is not a reconstruction of past PRs.
Some diagnostic logs referenced by local documents intentionally remain local.

If Git lacks an author identity, set your chosen name and GitHub-provided email with
`git config --local`, using the address shown in your GitHub email settings. Do not change global
Git configuration merely for this project. Create the local import commit, connect it to GitHub,
and merge the repository's starter commit before pushing:

```bash
git commit -m "Import LedgerX financial demo developed locally"
git remote add origin https://github.com/anaselmadhi/LedgerX.git
git fetch origin
git merge origin/main --allow-unrelated-histories
git push -u origin main
```

If the merge reports conflicts, resolve them before pushing; do not use `--force`. If `origin`
already exists, inspect it rather than overwriting it. GitHub authentication is completed on your
computer through your configured credential manager, browser login or SSH setup; never paste a
token into this document.

On GitHub, open **Actions → LedgerX verification** and inspect both `verify` and
`container-browser` jobs. A configured workflow is not a successful run. Save the real run URL
and result before recording a new revision as verified. The first published commit `d65fb3c`
passed both jobs in run #1, as reported in the owner-supplied summary. Later commits and PR heads
must have their own successful checks; this first result does not cover subsequent changes.

## Current changes to review

These are descriptions of actual changes in the working directory. They can be grouped as commits
if an earlier baseline is available; otherwise include them transparently in the initial import.
Do not pretend these PRs existed before the project was published.

| Change | Reviewer question | Validation |
|---|---|---|
| Bound expensive authentication requests | Do login/signup share limits, and can simultaneous requests exceed the KDF cap? | Six dedicated tests and the full 115-test backend release passed on schema 0003 |
| Prepare the Docker application for hosted startup | Does the default build launch the API, respect `PORT`, preserve locked dependencies and stop on migration failure? | Startup/config tests and production-container smoke/browser checks passed on schema 0003 |
| Exercise two customer browser sessions against Docker | Can two owners transfer/refund while sessions remain independent and accounting balances? | Both live journeys passed within the 12/12 browser suite on schema 0003 |
| Document the public demo setup | Are secrets, hosted/local data and the evidence boundaries clear? | Guide and configuration reviewed locally; first public deployment pending |

The subsequent schema `0004` projection and fixed-arrival benchmark are another concrete change.
The host release passed 149 backend tests, 26 frontend tests and 12 production-container browser
cases. Latency measurements include generator drops at higher offered loads; see
[LATENCY_RESULTS.md](LATENCY_RESULTS.md). The `0004` evidence is archived under
`artifacts/releases/2026-10-22-projection/`, separately from `0003`. Check the published
[Actions workflow](https://github.com/anaselmadhi/LedgerX/actions) for the remote result.

## Later PRs

Use one branch per concrete improvement, such as a reproducible browser bug, account-list usability
or a measured query optimization. Include a minimal example, the resulting behavior, actual test
output and any migration/compatibility concern. Open a PR, let CI run and inspect the diff before
merging. A small number of useful, well-explained PRs is stronger evidence than a fabricated history.

The source and dates are separate from authorship claims: the project documentation acknowledges
AI assistance. Prepare to explain and change the code yourself during an interview.
