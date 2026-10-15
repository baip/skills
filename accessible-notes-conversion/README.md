# accessible-notes-conversion

The source of the `accessible-notes-conversion` skill, one folder of the
`skills` repository. A notes project that uses it, such as the ChE 621
notes, keeps a clone of `skills` beside its own working copy and links this
folder in as `skill/`, which the project ignores:

```
ln -s ../skills/accessible-notes-conversion skill   # once, from the project's working copy
```

## What is here

| Path | What it is |
|---|---|
| `SKILL.md` | the skill itself: when to use it and the workflow |
| `references/` | the longer guides `SKILL.md` points to, and the templates for a project's `CONVENTIONS.md` and `BUILD.md` |
| `scripts/` | tools run from the skill: `init_project.py`, `render_pages.py`, `contact_sheet.py`, `notation_lint.py` |
| `assets/toolkit/` | the build scripts and LaTeX class a project gets |
| `assets/templates/` | `contents.yaml`, the example lecture and its drawing script, `.gitignore`, `package.json` |

`README.md` is not part of the skill and is left out of the package. The
installable `.skill` file is built by `package.py` at the repository root,
which packages every skill in the repository.

## Making a change

1. Edit here (or through the project's `skill/` link) and commit in the
   `skills` repository.
2. Try it in the notes project. From the project's working copy:

   ```
   python3 skill/scripts/init_project.py . --update-toolkit
   ```

   This copies the build scripts into the project. Build and check as
   usual, and commit the result in the project, naming the skill commit
   it came from (`git -C skill log -1 --format=%h -- .`, which leaves out
   commits that touch only the repository's other skills).
3. Package and install:

   ```
   python3 package.py accessible-notes-conversion   # from the repository root; writes dist/accessible-notes-conversion.skill
   ```

   Open the `.skill` file in the Claude app and save it to replace the
   installed version. The file is a build product and is not committed.

## Testing a change

- `python3 scripts/init_project.py /tmp/try --title "CHEM 101 — General Chemistry" --short "CHEM 101"`
  scaffolds a fresh project; build its example lecture to check the
  toolkit end to end.
- In the notes project, regenerate every document's LaTeX before and after
  `--update-toolkit` and compare. Only the header line should differ.
