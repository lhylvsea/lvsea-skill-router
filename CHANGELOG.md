# Changelog

## 0.2.0 - 2026-10-14

- Unified explicit JEV routing and optional human confirmation under `$lvsea-skill-router`.
- Reuse one catalog and rerank result across the confirmation boundary; label local fallback separately from Jev probabilities.
- Disable implicit invocation and exclude the router itself from downstream candidates.
- Keep `$codex-jev-gate` as an optional separate Codex skill; route requests through the canonical `$lvsea-skill-router` entry and use its built-in confirmation mode.

## 0.1.0 - 2026-09-23

- Added Codex/Agent multi-root Skill discovery and name de-duplication.
- Added a local six-axis context-cost approximation based on the public Skill Grader methodology.
- Added bounded shortlist generation for `jev_rerank` followed by `jev_decide` with escape hatches.
- Added Chinese README, usage guide, offline tests, package validation, and routing evaluation cases.
