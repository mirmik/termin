---
name: prepare-ready-cards
description: Triage Termin Kanboard cards from Backlog, verify their relevance against the current repository and board history, clarify scope and acceptance, promote small unblocked executable work to Ready, and retire or redirect stale and already-implemented cards. Use when Codex should prepare the backlog for execution, find straightforward work for Ready, clean up outdated cards, or run a backlog grooming pass without implementing the selected tasks.
---

# Prepare Ready Cards

Prepare a trustworthy `Ready` queue from Termin's `Backlog`. Do not implement the cards during this pass.

This skill extends `kanboard-taskboard`. Before changing the board, read that skill and `docs/taskboard-guidelines.md`. Use the project name `termin` with its taskboard CLI. For a multi-card pass, export Backlog cards with comments and tags once, then inspect promising or questionable cards individually.

## Outcome

Leave each reviewed card in one truthful state:

- `Ready`: directly executable without preliminary investigation or decisions;
- `Backlog`: still valuable, but unclear, blocked, broad, or dependent on other work;
- `On Test`: the implementation appears complete, but a concrete manual, platform, or human verification remains;
- `Done`: acceptance is already satisfied and required verification is evidenced;
- updated in place: the card remains in its column after its description, tags, or scope are made current.

Prioritize finding `size:XS` and `size:S` work, plus narrowly bounded `size:M` work. Do not optimize for the number of cards moved.

## Review Workflow

1. List or export cards in `Backlog`, including tags and comments.
2. Prefer likely small tasks with a concrete title; also inspect suspiciously stale, duplicate, or apparently completed cards.
3. Read the full card and recent comments.
4. Search the current code, tests, documentation, git history when useful, and related board cards. Treat card wording as a hypothesis, not proof of current state.
5. Decide the disposition using the gates below.
6. Update the description when comments or repository reality have changed the effective task. Use `kanboard-api updateTask` only when the high-level CLI lacks the needed edit operation.
7. Add a concise comment when changing workflow state or when the reason is not self-evident.
8. Move or close the card, then read it back to verify the result.

For a large batch, inspect first and use `--dry-run` before batch moves or closes. Process cards in bounded groups and report progress.

## Ready Gate

Move a card to `Ready` only when all conditions hold:

- the problem or requested change still exists in the current tree;
- scope names one coherent, closable unit of work;
- acceptance states an observable completion condition;
- the likely implementation area is identifiable;
- no architecture/product decision or ambiguous reproduction must happen first;
- no unresolved dependency, external event, hardware gate, or human answer blocks implementation;
- one focused execution pass can reasonably finish it;
- tags include an honest size, normally `size:XS`, `size:S`, or a bounded `size:M`.

If minor editorial work makes an otherwise clear card ready, update it and promote it. Do not invent requirements or silently choose a consequential architecture decision.

## Other Dispositions

Keep a card in `Backlog` when it needs investigation, decomposition, an owner decision, prerequisite work, or a clearer reproduction. Update `Current state`, `Remaining`, `Blocked by`, and `Verification` where useful. Comment with the concrete missing fact or decision; avoid vague statements such as "needs clarification".

For umbrella or `size:L`/`size:XL` cards, keep the umbrella in `Backlog` and identify live child work. Create or update child cards only when the decomposition is evident and non-duplicative. Promote only independently executable children.

Close a card as `Done` only with strong evidence that its acceptance is already satisfied and required verification has passed. Cite the code, test, commit, replacement card, or current behavior in the closing comment. Age, missing code matches, or intuition alone is not enough.

Move a card to `On Test` when implementation evidence exists but a specific manual, device, platform, or human check remains. Put the exact environment and verification scenario in the description or comment.

When a card describes obsolete architecture or has been superseded, update it if a real remaining task survives. Otherwise close it with the reason and, when applicable, a link or ID for the replacement. For duplicates, preserve the authoritative card and reference it from the duplicate before closing.

## Guardrails

- Do not modify source code as part of backlog preparation, except when the user separately requests implementation.
- Do not move uncertain work to `Ready` merely because it looks small.
- Do not close cards based only on a shallow text search; distinguish renamed, migrated, and partially completed behavior.
- Do not use `On Test` as a generic holding column. Name the outstanding verification.
- Do not leave the current task definition scattered across comments; make the description authoritative.
- Do not create new cards for trivial editorial gaps that can be fixed on the existing card.

## Report

Summarize each reviewed card with its ID, resulting state, and short rationale. Separately list cards promoted to `Ready`, retired or sent to `On Test`, and left blocked in `Backlog`. Call out uncertain findings and board/code smells without overstating them.
