# No Owner-Thread Restrictions

## Status

Accepted engine-wide rule.

This note supersedes every earlier recommendation that exposes creator-thread,
owner-thread, UI-thread, scene-thread or render-thread affinity as a
precondition of an engine API. Earlier documents remain valid for ownership,
lifetime, transaction and ordering decisions, but not for thread-identity
checks imposed on callers.

## Decision

Owner-thread restrictions are prohibited in Termin.

An engine operation must not fail, assert, log an error or become undefined
merely because it was called from a thread different from the thread that
created an object or initialized a subsystem. In particular, code must not:

- capture a creator thread ID and later compare calls against it;
- install mutation-thread checkers such as
  `Live module mutation must run on the integration owner thread`;
- require application, editor, Python or plugin code to marshal an otherwise
  valid operation to a privileged thread;
- expose generic `defer(callback)` queues that hide when and where application
  work will execute;
- use owner-thread affinity as a substitute for synchronization, immutable
  snapshots, transactional publication or explicit lifetime management;
- document a public method as safe only on an implicit owner/UI/render thread.

Existing restrictions of this kind are architectural debt and must be removed
from the engine, bindings and application code. New ones must not be added.

## Required replacement model

Thread safety belongs to the subsystem that owns the state, not to its callers.
Depending on the operation, the implementation must use one or more of:

- immutable input snapshots and prepared results;
- atomic batch/commit publication;
- explicit locking around shared mutable state;
- explicitly named subsystem executors at genuine external concurrency
  boundaries, with documented execution and completion semantics;
- versioned handles and liveness validation;
- synchronous completion or an explicit future/result for asynchronous work;
- deterministic teardown that coordinates in-flight operations.

Serialization is allowed as an internal implementation detail. Thread affinity
is not. A graphics backend, platform API or foreign library that itself has
thread constraints must be isolated behind an adapter that accepts calls from
arbitrary threads and performs the required internal serialization. That
constraint must not leak upward as an engine-wide caller obligation.

## Current execution policy

Removing thread affinity does not authorize application code to create
background threads ad hoc or to let a callback accidentally inherit the thread
of the preceding operation.

Until Termin has an explicit job/executor architecture, editor startup, module
preparation, module publication, project initialization and scene loading run
synchronously on the calling thread. Long-running operations report progress
through callbacks. A progress callback updates the presentation model and may
present an intermediate UI frame without moving the operation itself to another
thread.

Generic UI deferral is prohibited. Event handlers invoke their actions directly;
controllers publish progress directly through signals or callbacks. A queue may
exist only at an unavoidable and explicit concurrency boundary, such as an MCP
server handing a request to an engine executor. Such a queue is part of the
subsystem protocol, not an application-level escape hatch named `defer`.

Future parallel execution requires an explicit design for task ownership,
dependencies, cancellation, completion, error propagation and publication.
Concurrency must be introduced at that subsystem boundary, not by wrapping an
existing synchronous call chain in `threading.Thread`.

## Error policy

Errors must describe the actual failed operation or resource condition.
Messages such as `must run on the owner thread`, `wrong thread` and
`thread-affinity violation` are not acceptable runtime outcomes. They indicate
an unfinished migration in the engine itself.

Removing a thread check without making the underlying state safe is also not
acceptable. The check and the unsafe ownership assumption must be eliminated
together.

## Immediate migration targets

The first mandatory cleanup targets are:

1. Remove `ModuleRuntime::MutationThreadChecker` and
   `TermModulesIntegration` owner-thread validation.
2. Make module discovery, load, unload, reload and shutdown safe through
   transaction boundaries and subsystem-owned synchronization.
3. Remove editor-side owner-action/defer choreography whose only purpose is to
   satisfy module-runtime thread identity.
4. Audit scene, resource, render, GUI, MCP and window code for creator-thread
   checks and replace them with internal coordination.
5. Update tests: tests must verify concurrent correctness and deterministic
   ordering, not rejection of calls from a non-owner thread.

The repository should contain no engine diagnostic enforcing owner-thread
affinity when this migration is complete.
