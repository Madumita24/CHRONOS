# CHRONOS Phase 6.5 Certification Architecture

## Objective

Phase 6.5 is an independent release gate over the four existing Phase 6
engines. It answers whether an independent reviewer can trust CHRONOS to
analyze supported data-platform changes, preserve evidence and uncertainty,
generate only bounded evidence-backed repair candidates, and leave the Phase
1-5 golden behavior unchanged.

The gate is evidence based. It rebuilds final fixtures, checks manifests and
fingerprints, verifies cross-phase identities, exercises tamper and failure
boundaries, scans portability and security properties, and exports one
deterministic 32-artifact package. Engine self-certification is necessary but
is not sufficient by itself for the Phase 6 release decision.

## Scope

The certified scope is:

1. Phase 6.1 deterministic structural counterfactual analysis;
2. Phase 6.2 deterministic SQL/dbt semantic analysis;
3. Phase 6.3 deterministic bounded multi-file repository analysis;
4. Phase 6.4 deterministic repair-candidate generation and static projection.

The certification explicitly excludes runtime correctness, business approval,
safe-to-merge status, warehouse execution, dbt execution, orchestration
execution, downstream consumer behavior, DataHub write-back, and frontend
scenario selection.

The resulting state is a release-readiness statement about the static Phase 6
boundary, not an execution certificate.

## Independence from feature engines

The certification layer lives under `chronos.phase6_certification`. It calls
the public Phase 6 APIs and public presentation service but does not alter the
Phase 6.1-6.4 feature implementations. It uses their exported artifacts as
inputs and independently checks:

- exact package names and counts;
- manifest closure and semantic fingerprints;
- producer and consumer identities;
- replayed outcomes;
- deterministic repetition;
- golden and fixture non-mutation;
- portability and security controls;
- conservative vocabulary and dimension separation;
- test evidence and working-tree classification.

Two defects discovered during implementation were confined to the new
certification layer: the Phase 5 DTO identity field was initially addressed by
the wrong attribute, and leading whitespace in Git porcelain output was
initially stripped. Both were corrected without changing a feature engine.

## Trust chain

The certified chain is:

```text
Phase 6.1 structural contracts ----+
                                    +--> Phase 6.3 PR package
Phase 6.2 semantic contracts -------+            |
                                                 v
                                  Phase 6.4 predecessor trust gate
                                                 |
                                                 v
                                  isolated repair candidate preview
                                                 |
                                                 v
                                  unchanged Phase 6.3 static replay
```

For each handoff, Phase 6.5 checks the relevant engine/model/parser version,
snapshot identity, repository and BASE/HEAD identity where applicable,
manifest and artifact fingerprints, and exact file/group/root/action
references. Prose and copied summaries are not accepted as evidence.

## Replay strategy

Every final fixture is run twice in a repository-contained temporary
workspace:

- Phase 6.1: rename, delete, and type change;
- Phase 6.2: aggregation, combined aggregation/filter, filter, join, and
  derived expression;
- Phase 6.3: primary incomplete, coherent, no-material, and conflict;
- Phase 6.4: primary, coherent, no-material, conflict, explicit deletion, and
  type alignment.

The two semantic fingerprints must match. Phase 6.4 patch fingerprints must
also match. Outputs are deleted after evidence is extracted. Frozen artifacts,
examples, source, tests, frontend, and analyzed bundles are hashed before and
after replay.

## Capability matrix

The machine-readable matrix distinguishes `SUPPORTED`,
`SUPPORTED_WITH_LIMITATIONS`, `UNSUPPORTED`, and `OUT_OF_SCOPE`. Each row binds
one capability to an owning phase, input and output contract, evidence source,
deterministic parser/rule, compatibility and decision dimensions,
certification artifact, and known limit.

Automatic semantic-intent repair is explicitly unsupported. Runtime
verification is explicitly outside Phase 6.

## Vocabulary consistency

The vocabulary artifact assigns one bounded meaning to structural
compatibility, semantic change, repository coherence, evidence uncertainty,
PR disposition, repair disposition, repair completeness, and static
projection. It permits `STATIC_PROJECTED` and `PROJECTED_POST_REPAIR` only as
non-runtime projections.

`VERIFIED_REPAIR`, `SAFE_TO_MERGE`, and `EXECUTION_PASSED` may appear only in
the vocabulary/dimension audit as prohibited claims. They cannot appear as an
outcome in any other certification artifact.

## Dimension separation

Twelve dimensions remain independent:

1. structural compatibility;
2. semantic compatibility;
3. repository coherence;
4. execution validity;
5. evidence certainty;
6. severity if realized;
7. business/context criticality;
8. PR disposition;
9. repair disposition;
10. repair completeness;
11. static projected state;
12. runtime verified state.

The gate directly asserts that coherent repository references do not prove
semantic compatibility, a ready repair candidate does not prove merge safety,
a statically blocking incompatibility does not prove a runtime failure, and a
static projection is not runtime verification.

## Golden gate

The 16 root JSON artifacts are byte-hashed before and after all replay work.
The gate also reconstructs the Phase 5 `CHRONOS-DEMO-001` review through its
public certified artifact loader.

Required anchors are:

- Phase 4 physical SHA-256:
  `5dc730bae390908fa14f5ee5dc5d6a2b6a71382eecf664950bf60f76a74c94e8`;
- Phase 4 semantic fingerprint:
  `sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`.

Any difference produces a failed certification state.

## Determinism and portability

Semantic identity excludes output directory, execution time, clone location,
temporary workspace, safely normalized line endings, semantically irrelevant
formatting/comments, and safely canonicalized YAML ordering. The gate records
the two fingerprints for every fixture and both patch fingerprint maps for
every repair fixture.

All replay artifacts, patches, and candidate previews are scanned for absolute
paths, Windows drive prefixes, machine usernames, temporary directories,
secrets, private keys, authenticated URLs, prohibited raw source, semantic
timestamps, and unstable serialization.

## Security architecture

The security matrix covers strict proposal parsing, Git argument and revision
handling, repository/bundle containment, symlink and non-regular-file
rejection, binary and UTF-8 checks, resource limits, YAML safe loading and
duplicate-key rejection, SQL and Python AST boundaries, Jinja rejection,
exact parser/editor targeting, patch path and isolated-application checks,
overwrite recognition, atomic staging and cleanup, credential detection,
bounded CLI errors, and the absence of repository-code execution and DataHub
writes.

Phase 6.5 itself invokes only CHRONOS static APIs. It does not execute fixture
SQL, dbt, DAGs, pipelines, or consumers.

## Tamper and failure testing

The package loader requires exactly 32 regular JSON files, strict duplicate-
key-free JSON, shared release/version headers, exact manifest ordering and
fingerprints, consistent certification state, and portable credential-free
content. Artifact, identity, graph/path, root/group/action, patch/candidate,
protected-semantics, manifest, and certification tampering all fail closed.

Expected failures are classified without stack traces or partial output as
input validation, identity mismatch, ambiguous resolution, unsupported syntax,
insufficient evidence, certification failure, tamper detection, unsafe path,
resource limit, conflict block, or no supported repair.

## Release manifest and decision

The release manifest binds the feature source commit and tree, engine and
certification versions, working-tree classification, supported/unsupported
capabilities, public interfaces, proposal/package contracts, parser/editor
versions, golden and fixture fingerprints, actual test totals, skipped-test
summary, security summary, limitations, Phase 7 requirements, and the top-
level decision.

Allowed decisions are:

- `PHASE_6_CERTIFIED`;
- `PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS`;
- `PHASE_6_NOT_CERTIFIED`.

The current offline gate uses `PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS`
because seven live DataHub-dependent tests are intentionally skipped. This is
non-blocking for the frozen static Phase 6 scope but means live service drift
was not revalidated.

## Non-goals

Phase 6.5 introduces no new analysis operation, semantic delta, parser, DAG
framework, repair rule, UI, GitHub integration, patch application, runtime
validation, DataHub/MCP/Skill integration, LLM analysis, or DataHub write. It
does not begin Phase 7, Phase 8, or Phase 9.
