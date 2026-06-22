---
type: Specification
title: Open Knowledge Format (OKF) Conformance & Mapping
description: How the option-wizard reference knowledge base maps to the Open Knowledge Format v0.1 — type vocabulary, frontmatter schema, and bundle conventions.
tags: [okf, conformance, schema, meta]
timestamp: 2026-06-22T15:49:54Z
---

# Open Knowledge Format (OKF) Conformance

This `references/` tree conforms to **[Open Knowledge Format (OKF) v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)** — an open, vendor-neutral standard for portable, agent- and human-readable knowledge. An OKF bundle is a directory of markdown "concept" files, each carrying YAML frontmatter, cross-linked into a graph via relative markdown links, and navigated through reserved `index.md` files. No SDK, runtime, or proprietary account is required to produce or consume it.

Background: [How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/) (Google Cloud).

> **Provenance note.** The OKF v0.1 spec and the Google Cloud announcement are cited as the upstream's published references; this repo treats them as the format source but does not independently vouch for their content. The format is adopted on its mechanics (markdown + YAML + relative links), which stand on their own regardless of provenance.

## What is the bundle?

The `references/` tree is the curated, shareable OKF bundle that ships with the option-wizard skill. The trader's private archive under [`private/`](private/) (gitignored — personal NLV, positions, journal) is a second, parallel bundle built on the same concept-=-file convention but **never committed**; it is not formally conformance-checked because it holds raw account data, not curated concepts. Both are plain markdown — version-controllable, renderable on GitHub, parseable by any agent.

## Why OKF fits this repo

The skill was already built on the OKF design pattern before adopting the name:

- **Concept = file.** Each pitfall, case study, framework, and runbook is one markdown file; its path is its identity (URI).
- **Cross-linked graph.** Pitfalls ↔ case studies ↔ frameworks ↔ runbooks reference each other with relative markdown links.
- **Progressive disclosure.** `SKILL.md` → the §"When to read which file" router → individual concepts, loaded lazily only when a situation fires.

Adopting OKF v0.1 formalizes this: it adds the OKF-standard frontmatter fields, the reserved `index.md` / `log.md` filenames, and this conformance contract.

### The router stays primary; frontmatter `description` is the fallback

OKF's lazy-load model is "read a file's frontmatter `description` to decide whether to load it." option-wizard already has a **stronger** primary mechanism: the `SKILL.md` §"When to read which file" table, a *situation → file* router loaded on every turn ("when PB quotes an FCN, read `fcn-framework.md`"). That table is not replaced. The frontmatter `description` is the **per-file self-description** — the fallback for a freshly added concept the router does not yet name, and the human/tooling-facing summary. Both coexist by design.

## Frontmatter schema

Every concept file carries a YAML frontmatter block. OKF v0.1 requires only `type`; this repo additionally always sets OKF's recommended fields (`title`, `description`, `tags`, `timestamp`) plus domain-specific **extension fields**. OKF is minimally opinionated — producers may define their own content model, so the extension fields coexist with the standard ones.

| Field | OKF role | Set here | Notes |
|---|---|---|---|
| `type` | **required** | always | Concept type — see the vocabulary below |
| `title` | recommended | always | Human-readable title |
| `description` | recommended | always | One-line relevance summary; what an agent reads to decide whether to load the file |
| *(extension fields)* | producer-defined | varies | `severity`, `appliesTo` on pitfalls; `ticker`, `event`, `date`, `status`, `result`, `structures` on case studies |
| `tags` | recommended | always | YAML array, e.g. `[macro-hedge, vix]` |
| `timestamp` | recommended | always | ISO 8601 UTC — the document's last-updated time (sourced from git history) |
| `resource` | recommended | conditional | URL of an underlying real-world resource. Omitted for self-describing curated concepts |

**Field order** is: `type`, `title`, `description`, then extension fields, then `tags`, `timestamp` (and `resource` where present).

**Body convention.** Frontmatter is *additive*: the existing prose body of each concept is unchanged. Pitfall bodies keep their `**Date:** / **Ticker:** / ## What I did` structure; case-study bodies keep `**Date:** / **Setup:** / ## Data snapshot`. The frontmatter `timestamp` (document last-updated) and a body `**Date:**` (the trade/analysis date) are different fields and may legitimately differ.

## Type vocabulary

| `type` | Concept | Location |
|---|---|---|
| `Framework` | always-relevant decision framework ("given regime X, pick Y") | `strategies.md`, `gamma-framework.md`, `price-action-framework.md`, `macro-hedge-convexity.md`, `index-premium-selling.md`, `aq-dq-framework.md`, `fcn-framework.md` |
| `Runbook` | operational step-sequence / process spine ("do these steps in order") | `analysis-runbook.md`, `workflows-overview.md`, `execution.md`, `review-framework.md` |
| `Reference` | source-of-truth policy / reference doc | `data-sources.md` |
| `Trading Pitfall` | analytical-bias rule distilled from a closed trade | `pitfalls/NN-*.md` |
| `Trade Case Study` | closed / example trade post-mortem | `ticker/*.md` |
| `Template` | copy-source for a new concept | `pitfalls/_template.md`, `ticker/_template.md` |
| `Index` | directory navigation index | `index.md` (root + every subdir) |
| `Changelog` | chronological change history | `log.md` |
| `Specification` | this document | `OKF.md` |

`Trading Pitfall` and `Trade Case Study` are kept **byte-identical to the upstream [trade-skills](https://github.com/himself65/trade-skills) vocabulary** so a pitfall or case study lifted from that bundle pastes in without reformatting. `Framework` / `Runbook` / `Reference` are option-wizard producer extensions.

### Extension fields by type

- **`Trading Pitfall`**: `severity` (`HIGH` | `MED` | `LOW`), `appliesTo` (comma-separated trade types the rule guards).
- **`Trade Case Study`**: `ticker`, `event`, `date`, `status` (`closed` | `open` | `in-progress` | `example`), `result`, `structures` (YAML array).

## Bundle conventions

- **Identity = path.** A file's path is its concept URI. Links between concepts are relative markdown links (e.g. `../ticker/orcl-2026-06-fcn.md`), forming the knowledge graph.
- **`index.md` is the canonical navigable index** (OKF reserved name). To preserve GitHub's directory-level rendering, each subdirectory also keeps a one-line `README.md` stub that points to its `index.md`.
- **`log.md`** (OKF reserved name) records the knowledge base's chronological evolution — see [`log.md`](log.md).
- **Bundle entry point** is [`index.md`](index.md) at the `references/` root, which links out to every sub-area.
- **Portable.** The bundle ships as a git repo / tarball; nothing here depends on a specific cloud, model provider, or agent framework.

## Conformance checklist (new concept)

When adding a pitfall, case study, framework, or runbook:

- [ ] File has YAML frontmatter with at least `type`.
- [ ] `title`, `description`, `tags` (array), and `timestamp` (ISO 8601 UTC) are set.
- [ ] Extension fields for the type are filled (see `_template.md` in the directory).
- [ ] Cross-links to related concepts use relative markdown links.
- [ ] A row is added to the directory's `index.md`.
- [ ] A dated entry is added to [`log.md`](log.md).
- [ ] For pitfalls/case studies promoted from `private/`: every account-specific number (NLV, position size, fills) is stripped first.

## OKF spec & tooling

- **Spec, reference bundles, and tooling:** https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf
- **Announcement:** https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/
- **Upstream that this bundle borrows the pattern from:** https://github.com/himself65/trade-skills
