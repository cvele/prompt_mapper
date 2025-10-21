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

## Core Flow (Simplified)

For each movie file in directory:

1. **Check if Movie File**
   * Verify file is a video file (by extension and size)
   * Skip if not a valid movie file

2. **Clean Filename**
   * Use Radarr-style cleaning logic
   * Extract movie name and year from filename
   * Remove quality indicators, codecs, release groups, etc.

3. **Search TMDb**
   * Search TMDb using cleaned movie name and year
   * Return top N candidates (default: 10)
   * Rank by deterministic scoring (title similarity, year proximity, popularity, language match)

4. **LLM Selects Best Match**
   * Send TMDB candidates to LLM with original filename context
   * LLM analyzes and selects the best matching candidate
   * Returns selected candidate and confidence score (0.0-1.0)

5. **Confidence Check**
   * If confidence ≥ 0.95 (configurable threshold): Auto-select
   * If confidence < 0.95: Request manual selection from user
   * Manual selections have confidence = 1.0

6. **Manual Selection UI** (if needed)
   * Display original filename as hint
   * Show numbered list of TMDB candidates
   * User types number to select or 's' to skip

7. **Add to Radarr**
   * Check if movie already exists in Radarr by TMDb ID
   * If exists: Skip (already in library)
   * If not exists: Add movie to Radarr
   * Optional: Request confirmation unless --auto-add flag is used

8. **Report & Continue**
   * Display result for this file
   * Continue to next file
   * Show session summary at end

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

* **Privacy**: Send only filename, cleaned movie name, and year to LLM (no full paths)
* **Safety**: Manual review required for confidence < 0.95 (default threshold)
* **Simplicity**: KISS - simple for-loop processing, no batching, no dry-run mode
* **SOLID**: Clean separation of concerns with dependency injection

## Processing Model

* **File-by-file iteration**: Process each movie file individually in a directory
* **Interactive mode**: Request manual selection when confidence is below threshold
* **Auto-add mode**: Skip Radarr confirmation prompts with --auto-add flag

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
