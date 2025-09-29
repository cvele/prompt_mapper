Got it — let’s generalize it to **prompt-driven matching** (any language, any heuristic the user encodes).

# Functional Definition: “Prompt-Based Movie Mapper” (Radarr-assisted)

## Purpose

Enable users to reconcile locally stored movie files/folders with canonical entries by supplying their **own natural-language prompt** that instructs an LLM how to interpret names and context. The tool uses that LLM output to locate the movie on TMDb, sync with Radarr, and import via **hard-link** (default).

## Primary Goals

1. Let users define **arbitrary prompts** to steer title extraction/normalization (any language, style, or domain rule).
2. Convert LLM output into a **deterministic match** (TMDb ID).
3. **Upsert** into Radarr (add if missing (user confirm); use existing if present).
4. **Import** local files via Radarr (prefer hard-links).
5. Keep users in control for **ambiguous/low-confidence** cases.

## Users & Context

* **Power user / librarian**: Wants to apply custom rules (e.g., local naming conventions, festival titles, regional releases).
* **Collector**: Wants a semi-automated pass with minimal prompts.
* **Archivist**: Needs auditability, reversibility, and dry-runs.

## Inputs

* **Target path**: Directory containing one movie (or batch mode: many).
* **User prompt** (required per run or profile): Free-form text that explains how to interpret filenames/folders (e.g., languages, transliteration rules, year inference, edition/director’s cut hints, how to treat roman numerals, etc.).
* **Optional context**:

  * Locale(s) and preferred title languages.
  * Confidence threshold (0–1).
  * Radarr root folder, quality profile, tags, minimum availability.
  * Auto-add/auto-import toggles.
  * Dry-run toggle.

## Core Flow

1. **Scan & Parse**

   * Collect candidate filenames and folder name(s) under the target path.

2. **Prompt-Driven LLM Resolution**

   * Send the **user’s prompt** + observed names + any extracted hints (e.g., year tokens) to the LLM.
   * LLM returns a **structured result**:

     * `canonical_title` (string)
     * `year` (int or null)
     * `aka_titles` (array)
     * `language_hints` (array)
     * `confidence` (0–1)
     * `rationale` (string, short)

3. **TMDb Matching**

   * Search TMDb using `canonical_title` plus `aka_titles`, constrained by `year` if provided (±1 tolerance).
   * Rank candidates using deterministic scoring (title similarity, year proximity, popularity, original language match).
   * Produce **top-N** candidates with a **match score**.

4. **Decision**

   * If top candidate score ≥ user threshold and aligns with LLM `confidence` → select automatically (unless user forces review).
   * Else show a **review card** (poster, title, year, overview, alt candidates) for user choice: **Confirm / Choose Alternative / Skip**.

5. **Radarr Upsert**

   * Check Radarr for existing entry by TMDb ID.
   * If missing: **Add** with user’s profile/root/tags.
   * If present: reuse the existing movie entry.

6. **Import (Hard-Link Default)**

   * Trigger Radarr import for file(s) from the target path into the matched movie using **hard-link** strategy.
   * Report per-file results (imported, duplicate, already linked, skipped).

7. **Summarize & Continue**

   * Show a concise result (matched ID, actions taken) and proceed to next item (or end with a session summary).

## Prompts & Interactions

* **User Prompt** (free-form) examples:

  * “Titles may be in Serbian or Bosnian; translate to original/English; prefer festival titles if famous. Years in names are likely release years. Ignore release group tokens. Identify director’s cuts if explicitly noted.”
  * “Japanese titles in romaji; map to official English titles; if multiple adaptations, prefer the earliest feature film.”

* **System Prompts (built-in, not user-visible)** ensure the LLM always returns the strict schema above.

* **Review Cards** surface ambiguity (top 2–3 TMDb hits) with compact metadata.

## Rules & Heuristics

* Combine **LLM confidence** with **deterministic scorer**; both must pass threshold for auto-accept.
* Year tolerance ±1 (configurable).
* Skip **sample** or **extras** by duration/keywords.
* Prefer TMDb entries that list any **localized titles** matching user’s language hints.

## Error Handling

* **No confident LLM output** → ask user to refine the prompt or provide a manual title.
* **No viable TMDb match** → offer to: tweak search terms, adjust year, or skip.
* **Radarr offline** → offer identify-only mode; queue Radarr actions for later.
* **Import collision** (already linked) → show status and offer to skip/replace (if safe).

## Outputs

* **Per-item result**: local path, chosen TMDb ID, title/year, confidence scores, Radarr action (added/existed), import outcome, links (TMDb/Radarr).
* **Session summary**: totals for matched/added/imported/skipped + CSV/JSON audit log.

## Preferences & Policies

* **Privacy**: Send only sanitized strings + optional year to LLM (no full paths or PII).
* **Safety**: Default to review on low confidence; optional auto-mode only above threshold.
* **Reproducibility**: Store prompt + decisions in the audit log.
* **Undo**: Quick remove from Radarr (if newly added) and revert last import when feasible.

## Modes

* **Single-item mode**: One directory at a time (interactive).
* **Batch mode**: Process a queue; pause on ambiguities or collect them for later review.
* **Dry-run**: Resolve and rank only; no Radarr calls or imports.

## Success Criteria

* ≥90% correct matches without manual intervention when titles are reasonably informative.
* Clear, minimal prompts for the user; **ambiguous cases surfaced, not guessed**.
* Hard-link imports succeed without moving/deleting originals by default.
* Full audit trail for trust and repeatability.

## Extensibility (Later)

* Profiles: saved prompt + thresholds + Radarr defaults.
* Multi-source metadata (IMDB ID cross-checking).
* Fine-grained duplicate rules (edition, cut, remaster).
* Lightweight web UI over the same engine.
