---
name: ready-card-autopass
description: "Use when Codex should autonomously process Termin Kanboard tasks from the Ready column: select clear actionable cards, implement fixes, test, commit patches when useful, and move cards through the project workflow."
---

# Ready Card Autopass

Use this skill for autonomous passes over Termin Kanboard cards in the `Ready` column.

This skill extends the global `kanboard-taskboard` workflow. Before touching the board, read the `kanboard-taskboard` skill and `docs/taskboard-guidelines.md`. Select the `termin` project by name when invoking its bundled CLI.

## Goal Shape

A Ready autopass is a bounded work campaign:

1. Inspect `Ready` cards with tags, descriptions, and comments.
2. Choose one clear actionable card at a time.
3. Move the selected card to `In Progress` before implementation.
4. Implement and test the patch, committing when useful for the shape of the work.
5. Move the card based on the actual result.
6. Continue until no suitable `Ready` cards remain, the user stops the pass, or repeated blockers prevent useful progress.

Do not batch unrelated code changes into one card or one commit.

When processing multiple cards, commits are useful boundaries between completed tasks. A large card may likewise benefit from commits between meaningful implementation stages. For a single card whose changes naturally fit in one commit, leave the verified result uncommitted for the human to review and commit.

## Card Selection

Prefer cards that are mechanically or locally clear:

- explicit acceptance criteria;
- no unresolved architecture decision;
- no external hardware/manual-only blocker unless the user asked for that gate;
- expected scope fits one focused implementation pass;
- normally `size:XS`, `size:S`, or a well-bounded `size:M`.

Skip or triage cards that are vague, umbrella-shaped, missing acceptance, or unexpectedly broad.

For a genuinely difficult architecture choice, subtle cross-module risk, or a bug that resists the current diagnosis, consider a focused `better-call-sol` consultation before deciding how to proceed. Do not use it for routine implementation or mechanical verification.

## Execution Rules

If the fix is clear and mechanical:

- move the card to `In Progress`;
- make the change using normal repo conventions;
- run focused tests first, then broader tests when risk warrants it;
- update docs when behavior or workflow changed;
- when committing, use a concise message;
- do not add `Co-authored-by` trailers.

If the card is fully done and verification is sufficient:

- move the card to `Done`;
- add a short comment describing the implementation and verification;
- include commit hashes when available;
- do not leave the completed card in `In Progress` or `On Test` unless additional verification is still required.

If implementation is done but requires human/manual/platform verification:

- move the card to `On Test`;
- add a comment with the exact verification command, environment, or scenario required.

If implementation and available local verification are complete but CI cannot be run or its results cannot be obtained:

- do not treat unavailable CI as a blocker for completing the autopass goal;
- leave the card in `On Test`;
- add a comment recording why CI could not be run or checked and what CI verification remains.

If the card is only partially completed and further progress is blocked by remaining implementation work:

- leave or move it to `In Progress`;
- add a comment with completed work, remaining work, blocker, and verification already run;
- do not close it.

If the card turns out to have architecture questions or unclear acceptance:

- add a comment listing the concrete questions and what decision is needed;
- move it back to `Backlog`;
- do not implement speculative fallback behavior just to make progress.

If the card is stale, non-code, or mismatched with current code but review makes the needed action obvious:

- update the description/tags so the current scope and acceptance are explicit;
- either take it into `In Progress` and complete it, or move it back to `Backlog` with a comment explaining why it is not Ready.

## Hygiene

- Keep the board as task state, not a substitute for local verification.
- Do not leave completed cards outside `Done` "just in case"; use `On Test` only when concrete manual, visual, platform, or CI verification remains outstanding.
- If new scope is discovered, create or keep a separate card instead of stretching the current card.
- If comments change the meaning of a card, update the description so the current state is visible.
- Report bad smells, duplicate tasks, unfinished migrations, or suspicious stubs found during the pass. Create board cards only for meaningful follow-up work, not for trivial fixes already applied.

## Progress Reports

During a long goal, periodically report:

- current card id and title;
- action taken;
- tests or verification run;
- commit hash when available;
- resulting board state: `Done`, `On Test`, `In Progress`, or returned to `Backlog`.
