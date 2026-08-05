# CHRONOS Phase 7 Handoff Contract

## Purpose

This document defines the evidence Phase 7 must receive before any repair
execution or runtime validation begins. It does not authorize execution by
itself. Phase 7 requires explicit environment and execution authorization.

## Required inputs

Phase 7 must receive one mutually consistent evidence set:

- the complete certified Phase 6.4 repair package;
- the complete certified predecessor Phase 6.3 PR package;
- the original repository bundle or checkout identity;
- repository name/namespace/fingerprint and exact BASE/HEAD identities;
- repair proposal and selected root/group identities;
- repair action and Repair Plan identities;
- combined, file, and logical-group patch fingerprints;
- candidate file fingerprints and exact original HEAD fingerprints;
- parser/editor provenance and protected-semantics records;
- projected Phase 6.3 comparison;
- remaining findings and unresolved business/semantic questions;
- required Phase 7 validation list;
- approved dependency/environment policy;
- explicit human execution authorization.

The Phase 6.5 release manifest and top-level certification must validate before
the handoff is accepted. Copied prose or screenshots cannot replace any
machine-readable package.

## Independent Phase 7 obligations

Phase 7 must independently verify:

1. repository and BASE/HEAD identity;
2. patch fingerprints and clean patch application in a disposable checkout;
3. candidate file fingerprints after application;
4. dependency installation from the approved policy;
5. SQL parsing and authorized execution where applicable;
6. dbt parse/compile/test behavior where applicable;
7. schema and contract consistency;
8. DAG syntax, task identity, dependencies, and authorized framework checks;
9. quality/pipeline configuration validation;
10. application and repository tests;
11. data comparisons where authoritative fixtures or environments exist;
12. downstream consumer checks;
13. new root and conflict detection after execution evidence is added;
14. unresolved semantic/business intent and owner approval;
15. collection and fingerprinting of runtime evidence.

Phase 7 must produce a separate execution certification. It must never mutate
the Phase 6.3, 6.4, or 6.5 packages to make runtime results appear certified.

## Required environment policy

The execution environment must be disposable, isolated, repository-contained
or explicitly approved, credential-minimized, and auditable. Commands,
dependencies, environment variables, network access, data sources, and
external writes must be authorized before use. Secrets must not be embedded in
artifacts, command output, patches, or logs.

## Decision separation

Phase 6.4 `REPAIR_CANDIDATE_READY_FOR_REVIEW` or
`PARTIAL_REPAIR_CANDIDATE` means only that deterministic static generation was
certified. It does not mean the candidate applies in a new checkout, compiles,
runs, preserves data, satisfies consumers, has owner approval, or is safe to
merge.

Phase 7 must keep repair completeness, static projection, execution validity,
business approval, and release/merge decisions separate.

## Handoff rejection

Reject the handoff if any package is incomplete or tampered, identities differ,
fingerprints fail, protected semantics are unclear, remaining findings are
omitted, execution authorization is absent, or the environment policy is not
approved.

Phase 6.5 performs none of the Phase 7 validations listed above.
