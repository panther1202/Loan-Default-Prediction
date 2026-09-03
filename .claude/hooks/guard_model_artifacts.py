"""PreToolUse guard: refuse shell commands that would write a frozen model artifact.

ADR-0008 freezes the model, its preprocessing and its training data behind a
propose-then-approve gate. `permissions.deny` in .claude/settings.json already blocks the
Edit/Write tools on those paths, but it cannot see inside a Bash command -- and a one-line
`python -c "...open('model_params.json','w')"` writes the same file. This closes that gap.

Reads the PreToolUse payload on stdin, writes a deny decision to stdout, exits 0 either way.
Anything it does not recognise as a write is allowed, so a false negative degrades to the
status quo (the ADR gate) rather than to a broken shell.

ponytail: substring heuristic over the command text, not a shell parser. It catches the
plausible accidents -- a redirect, a sed -i, an rm, a script opening the file for writing --
and will miss a determined obfuscation (variable-built paths, base64, a heredoc into python).
Upgrade path if that ever matters: drop the heuristic and make the artifacts read-only on
disk, which no in-process guard can talk its way around.
"""

import json
import re
import sys

# Paths ADR-0008 protects: the training script, the exported parameters, the pickled model and
# preprocessing artifacts, and the training data directory. `(?<![\w.\-])` is a left boundary so
# `myapp.py` and `metadata/` do not match `app.py` and `data/`.
PROTECTED_PATTERNS = (
    r"(?<![\w.\-])app\.py",
    r"(?<![\w.\-])model_params\.json",
    r"(?<![\w.\-])[\w.\-]*\.pkl",
    r"(?<![\w.\-])data[\\/]",
)

# The sanctioned regeneration path. ADR-0008 step 3 requires model_params.json be rebuilt
# by this script, so a command that runs it is the policy working, not a violation.
SANCTIONED = "export_model_params.py"

# Tokens that indicate the command writes rather than reads. Kept deliberately broad;
# a read-only command (cat, head, git diff, grep) matches none of them.
WRITE_PATTERNS = (
    # Redirect. Excludes the arrows that show up constantly in prose and commit messages
    # (`->`, `=>`, `-->`); `<...>` spans are stripped before scanning, which is what keeps a
    # `Co-Authored-By: ... <noreply@example.com>` trailer from reading as a redirect.
    r"(?<![-=<>])>",
    r"\btee\b",
    r"\brm\b",
    r"\bmv\b",
    r"\bcp\b",
    r"\btruncate\b",
    r"\bdd\b",
    r"\bsed\b[^|]*-i",        # in-place sed
    r"\bshutil\.(move|copy)", # python
    r"\bopen\s*\([^)]*['\"][wax]", # open(path, 'w'/'a'/'x')
    r"\b(joblib|pickle)\.dump",
    r"\bto_(csv|json|pickle|parquet)\b",
    r"\bjson\.dump\b",
    r"\bwrite_text\b",
    r"\bSet-Content\b",
    r"\bOut-File\b",
    r"\bAdd-Content\b",
)


def mentions_protected(command):
    """Return the protected path the command names, or None.

    Plain substring search with a left boundary, rather than tokenising the command: quoting,
    escaping and redirection mangle tokens in too many ways to enumerate, and a guard that
    misses `open(\"model_params.json\",\"w\")` because of a stray backslash is no guard. The
    boundary keeps `myapp.py` and `metadata/` from matching `app.py` and `data/`.
    """
    lowered = command.lower()
    for pattern in PROTECTED_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            return match.group(0).lstrip("\\/'\" ")
    return None


def looks_like_write(command):
    # Strip <...> spans first. A commit message carrying both a protected path and a
    # `Co-Authored-By: ... <noreply@example.com>` trailer is the common case, and reading that
    # trailer's closing angle bracket as a shell redirect blocks legitimate work every time.
    scannable = re.sub(r"<[^<>\n]{0,200}>", " ", command)
    return any(re.search(p, scannable) for p in WRITE_PATTERNS)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # unparseable payload: allow, the ADR gate still stands

    if payload.get("tool_name") != "Bash":
        return

    command = (payload.get("tool_input") or {}).get("command") or ""
    if SANCTIONED in command:
        return

    target = mentions_protected(command)
    if not target or not looks_like_write(command):
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "ADR-0008: %s is a frozen model artifact. The model, its preprocessing and its "
                "training data change only after the change is described to Panth and approved -- "
                "this is a hard stop, not a notification. Read docs/adr/0008-model-change-policy.md, "
                "propose the change in chat, and wait. To regenerate model_params.json legitimately, "
                "run export_model_params.py, which is allowed and is its only sanctioned writer."
                % target
            ),
        }
    }))


if __name__ == "__main__":
    main()
