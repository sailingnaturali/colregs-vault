# colregs-vault

> ⚠️ **UNVERIFIED DRAFT — PENDING HUMAN REVIEW (Bryan).**
> The `requirements.yaml` decision table and the International rule prose in this repo were
> drafted by an automated assistant and have **NOT** been verified against authoritative sources.
> US Inland and Canadian rule prose are **NOT** yet transcribed. Do not rely on this vault for
> navigation until each row of `requirements.yaml` and each rule file is checked line-by-line
> against the source text and this banner is removed.

## What this is

Public-domain navigation-rules content feeding the [`colregs-mcp`](../colregs-mcp) server.
The server reads this directory via the `COLREGS_VAULT_PATH` environment variable. It holds:

- `rules/<regime>/rule-NN.md` — rule prose with YAML frontmatter (`number`, `regime`, `part`,
  `title`, `source_pdf`, `verified`). Powers `get_rule` / `search_rules`.
- `requirements.yaml` — the curated decision table mapping a vessel situation to the lights and
  shapes the rules require. Powers `required_signals` / `check_compliance`. **Safety-critical.**
- `regime-polygons.geojson` — coarse PNW polygons resolving which regime applies by position.
- `manifest.yaml` — source provenance.

## Provenance & licensing

- **International (COLREGS 72) and US Inland** — transcribed from the *USCG Navigation Rules and
  Regulations Handbook*, a US Government work in the **public domain**.
- **Canadian** — *Canadian Collision Regulations* under the Canada Shipping Act: Crown copyright,
  freely reproducible under the **Reproduction of Federal Law Order**.

Because both source bodies are freely reproducible, this vault is public (unlike the copyrighted
`pilotbook-vault`).

## Coarse-polygon caveat (v0)

`regime-polygons.geojson` uses three approximate bounding boxes, not real demarcation geometry:

- `canadian` — southern BC / Gulf Islands box.
- `inland` — US San Juans / Puget Sound box (a coarse stand-in for the 33 CFR 80 demarcation).
- International is the default when no polygon matches.

The two boxes **overlap slightly near the marine border** (≈ lat 48.65–48.7). The loader returns
the **first** matching polygon and `canadian` is listed first, so the overlap resolves to Canadian
waters — an acceptable v0 bias for the Gulf Islands cruising grounds. Refine against the real
international maritime boundary and 33 CFR 80 lines before relying on regime resolution near the border.

## Review checklist (BLOCKING — Bryan)

This vault is not trustworthy until every item below is done and the banner above is removed:

- [ ] Verify **each `requirements.yaml` row** against its cited rule (lights, shapes, `forbids`,
      length bands, regime scope). These rows drive the compliance engine.
- [ ] Verify **each International rule file** (`rules/international/rule-NN.md`) against the USCG
      handbook text; flip `verified: false → true` per file and fill `source_pdf`.
- [ ] Transcribe **US Inland** prose (`rules/inland/`) and any rule that differs from International.
- [ ] Transcribe **Canadian** prose (`rules/canadian/`) and the Canadian Modifications.
- [ ] Replace the coarse regime polygons with real demarcation-line geometry.
- [ ] Confirm the rules left as `PENDING` stubs (24, and the unscoped paragraphs of 27) are either
      transcribed or intentionally deferred.
