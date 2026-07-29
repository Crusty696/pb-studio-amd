## Executive Summary

**Finding:** `design-system-page-path-traversal`
**Severity:** LOW
**Confidence:** High
**CWE:** CWE-22, Improper Limitation of a Pathname to a Restricted Directory

The design-system persistence CLI accepts a free-form `--page` value, changes
only letter case and spaces, appends `.md`, and passes the result to a
truncating file write. Path separators, `..` components, drive-qualified
paths, rooted paths, and UNC forms remain meaningful to Windows path
resolution. A crafted page label can therefore redirect the page-override
write outside `design-system/<project>/pages/`, including outside the chosen
output directory when enough parent components or an absolute form are used.

This is a developer-workflow confused-deputy issue rather than a remotely
reachable application endpoint. The documented workflow encourages an agent
or developer to persist a page label while implementing a user-requested
page. If that label is copied from an untrusted prompt, the Python process
writes with the developer's filesystem permissions. Direct CLI operators
already able to select arbitrary commands or `--output-dir` values gain no
new authority from this bug.

I statically reviewed target revision
`b76937ddf341fb395f81e6936612329eca85c601`, bound snapshot digest
`f763…2f50`, and the three cited source/documentation paths. I did not execute
the trigger or any tests because validation is deferred until task T332. No
fix revision was available. The relevant T305–T328 working-tree diff does not
modify these paths, so this is a pre-existing weakness exposed by the T329
review, not a regression introduced by those repair edits. Repository history
shows the vulnerable persistence file in the tracked snapshot introduced on
2026-03-09.

## Background

UI/UX Pro Max provides a local design-system generator. Its documented
Master + Overrides workflow stores global rules in `MASTER.md` and optional
page-specific rules beneath a `pages` directory. The intended invariant is
simple: a page label names one direct child of that directory.

The developer workflow explicitly presents page persistence:

```bash
python3 .shared/ui-ux-pro-max/scripts/search.py "<query>" \
  --design-system --persist -p "Project Name" --page "dashboard"
```

`.agent/workflows/ui-ux-pro-max.md:63-86` says this creates
`design-system/pages/dashboard.md` and instructs agents to consult that file
when building a page. This documentation establishes the important trust
boundary: a page concept can originate in a user request, while the agent-run
tool has local developer permissions.

The CLI exposes the value without validation in
`.shared/ui-ux-pro-max/scripts/search.py:61-74`:

```python
parser.add_argument(
    "--page",
    type=str,
    default=None,
    help="Create page-specific override file in design-system/pages/",
)

args = parser.parse_args()
result = generate_design_system(
    args.query,
    args.project_name,
    args.format,
    persist=args.persist,
    page=args.page,
    output_dir=args.output_dir,
)
```

`argparse` enforces only that the value is a string. We therefore carry the
page label unchanged into `generate_design_system`, which forwards it to the
persistence function when `--persist` is set.

## Vulnerability Details

`generate_design_system` passes `page` directly to `persist_design_system`
at `.shared/ui-ux-pro-max/scripts/design_system.py:461-482`. The latter
constructs the intended hierarchy and then derives the output filename:

```python
base_dir = Path(output_dir) if output_dir else Path.cwd()
project_name = design_system.get("project_name", "default")
project_slug = project_name.lower().replace(" ", "-")

design_system_dir = base_dir / "design-system" / project_slug
pages_dir = design_system_dir / "pages"

design_system_dir.mkdir(parents=True, exist_ok=True)
pages_dir.mkdir(parents=True, exist_ok=True)

# ...
if page:
    page_file = pages_dir / f"{page.lower().replace(' ', '-')}.md"
    page_content = format_page_override_md(design_system, page, page_query)
    with open(page_file, "w", encoding="utf-8") as f:
        f.write(page_content)
```

The decisive lines are
`.shared/ui-ux-pro-max/scripts/design_system.py:527-531`. Lowercasing and
replacing spaces are cosmetic transformations, not pathname validation. They
leave both Windows separators and parent components intact. We can carry, for
example, a label shaped like `..\..\..\AGENTS` into this expression:

```text
<output-dir>/design-system/<project>/pages/../../../AGENTS.md
```

Normal filesystem traversal resolves that path to
`<output-dir>/AGENTS.md`, outside `pages_dir`. The forced `.md` suffix limits
the primitive to Markdown-named targets, but it also makes developer
instruction files such as `AGENTS.md` natural targets. The target parent must
already exist because the code creates only the intended hierarchy.

Absolute Windows operands are stronger. After `.md` is appended, a
drive-qualified or UNC operand remains absolute; joining it with
`pages_dir` discards the intended prefix. A rooted operand can similarly reset
the path beneath the current drive. No `resolve`, containment comparison,
basename restriction, or separator rejection restores the direct-child
invariant.

Finally, `open(..., "w")` creates a missing target or truncates an existing
one before writing generated page content. The attacker does not receive a
general arbitrary-byte write: content is produced by
`format_page_override_md`. The demonstrated primitive is a redirected,
generated-content overwrite/create of a writable `.md` file.

## Exploitability Analysis

The strongest realistic route crosses the prompt-to-developer workflow
boundary. We start with a request that supplies a crafted page name. If an
agent follows the documented recipe and maps that name mechanically to
`--page`, the local CLI treats it as a path operand. We then choose a writable
Markdown target whose parent already exists. On the common default where the
repository is the output directory, three parent components escape
`design-system/<project>/pages/` to the repository root. The write can replace
an instruction, policy, documentation, or other Markdown file with generated
design-system content.

An absolute drive or UNC form removes the need to count directory depth and
can target another writable location. Its reliability still depends on the
target platform being Windows, the parent/share existing, and the process
having write permission. UNC use can also cause an outbound filesystem access,
but this review did not validate authentication behavior or claim credential
disclosure.

A traversal that names a nonexistent intermediate directory is a useful dead
end: `mkdir` prepares only `design_system_dir` and `pages_dir`, so `open`
fails instead of creating arbitrary parent trees. Likewise, the appended
`.md` suffix prevents a straightforward overwrite of files with other
extensions. These constraints, the need for an agent or developer to forward
the label, and the absence of a network application entry point support LOW
severity. They do not restore the documented containment guarantee.

The separate free-form `project_name` and intentional `output_dir` surfaces
deserve variant review, but they are not needed to prove this finding and are
not treated here as additional vulnerabilities.

## Proof of Concept

The accompanying `poc/` directory is intentionally inert. It contains no
script and does not invoke the vulnerable CLI. `crafted-labels-and-dataflow.txt`
records representative labels and the source-derived path transformations.
This satisfies the T329 static-review boundary without creating or truncating
any file.

From the report directory, inspect it with:

```sh
cd poc
cat crafted-labels-and-dataflow.txt
```

Representative source-derived output is:

```text
PARENT_TRAVERSAL
page label: ..\..\..\AGENTS
constructed: <output-dir>\design-system\<project>\pages\..\..\..\AGENTS.md
resolved sink: <output-dir>\AGENTS.md
sink mode: w (create or truncate, then generated Markdown write)
```

No cleanup is required because the artifact performs no write. Do not pass
the crafted labels to the vulnerable program on a real checkout. Execution
and fixed-version regression validation belong to T332.

## Remediation

The invariant should be enforced before any filesystem mutation: `page` must
produce one filename component, and the resolved output must be a direct child
of the resolved `pages_dir`. Reject invalid input; do not silently strip path
syntax because distinct hostile labels could collapse onto the same file.

A minimal pattern using only the standard library is:

```python
import re
from pathlib import Path

_PAGE_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}\Z")


def page_override_path(pages_dir: Path, page: str) -> Path:
    label = page.strip()
    if not _PAGE_LABEL.fullmatch(label):
        raise ValueError("page must be a simple label without path syntax")

    slug = re.sub(r"\s+", "-", label.lower())
    root = pages_dir.resolve()
    candidate = (root / f"{slug}.md").resolve()
    if candidate.parent != root:
        raise ValueError("page override must remain inside pages directory")
    return candidate
```

`persist_design_system` should call this validation before creating
directories or writing `MASTER.md`, then use the returned path for the page
write. Early validation keeps a rejected request side-effect free. The CLI
should catch `ValueError`, print a concise error, and exit nonzero.

At T332, targeted regression tests should exercise the real CLI-to-sink path:

- accept `dashboard` and `Order History`, producing one direct child;
- reject `../`, `..\`, forward/backslash nesting, rooted paths,
  drive-qualified paths, and UNC paths;
- seed sentinel `.md` files outside `pages_dir` and prove invalid labels
  neither modify nor create them;
- prove invalid labels do not modify `MASTER.md`;
- compare the resolved candidate's parent with the resolved `pages_dir`;
- retain a static assertion that persistence uses the validated helper rather
  than reconstructing a filename from raw `page`.

## Summary

The page-override feature confuses a display label with a pathname.
`argparse` accepts arbitrary text, the generator forwards it unchanged,
cosmetic normalization preserves path syntax, and `open(..., "w")` turns the
result into a redirected Markdown create-or-truncate primitive. We showed
statically how parent traversal and Windows absolute forms escape
`pages_dir`, while also identifying the `.md` suffix, existing-parent,
permissions, and agent-forwarding constraints that keep severity LOW.

The durable fix is to validate a simple label before all writes and enforce a
resolved direct-child containment check at the sink. T332 should then verify
both successful benign persistence and absence of side effects for traversal,
rooted, drive-qualified, and UNC inputs.
