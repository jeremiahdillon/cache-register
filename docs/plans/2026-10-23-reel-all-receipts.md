# Plan: every receipt gets a slide in the root reel (2026-10-23)

## Goal

Below the root page's splash, the reel gives the newest `REEL_SIZE = 6` receipts (by `as_of`) a full
slide each and lists the rest as text under "Older receipts" (`src/cachereg/site.py`, `_reel_markup`).
There are 8 receipts, so two are already in the text list. The author wants every receipt shown as its
own slide for now. The text list should stay available as a ceiling for when there is much more content.

## Change

1. **`src/cachereg/site.py`:** set `REEL_SIZE = 100` (was 6) and reword its comment: a ceiling for later,
   not a limit in use today. The older-list markup and the `after = "older"` / `"end"` logic stay as they
   are. With fewer than 100 receipts every receipt gets a slide and the last slide's "More" leads to
   `#end` (the closing screen), the path already taken today with ≤ 6 receipts.
2. **`tests/test_site.py`:**
   - `test_reel_on_index_only_with_media_for_every_receipt` (builds `REEL_SIZE + 2` receipts): define
     `size = 3` and `monkeypatch.setattr("cachereg.site.REEL_SIZE", size)` before the fixture loop, so the
     overflow path (slides, then the older list, "More" chain ending at `#older`, CTA after the list) stays
     covered without building 102 receipts. Derive every value from `size`, including the ones now
     hard-coded for the newest fixture: `range(size + 2)` for the fixtures and copied media,
     `newest = f"topic-{size + 1}"` in place of `topic-7` (the media path, the `cacheregister.dev/…` link
     and the first slide's `aria-label`), and `f"#{size + 2:03d} · As of 2026-01-{size + 2:02d}"` in place of `"#008 · As of 2026-01-08"` (fixture
     `i` is dated `2026-01-{i + 1:02d}`, so the newest is `size + 1`). The older list stays
     `["topic-1", "topic-0"]`. Drop `REEL_SIZE` from the test's import if it becomes unused.
   - Add an assertion (or a small test) that under the default cap, 8 receipts give 8 slides, newest first,
     with no `class="older"` section and the last "More" pointing to `#end`.
   - `test_reel_without_older_receipts_has_no_list` stays as is.
3. **`docs/PLAN.md` §5 (site):** two clause edits in the reel sentence, the rest (stills, motion,
   `reel.js`) unchanged. "a scroll-snapped reel shows the newest receipts (by `as_of`), one per screen,"
   becomes "a scroll-snapped reel shows every receipt, newest first (by `as_of`), one per screen, up to a
   cap (`REEL_SIZE`, 100),"; and "older receipts are listed as text" becomes "receipts beyond the cap are
   listed as text". Keep "the older list" in the sentence about where "More" leads, since that path remains.
4. **`assets/site/site.css`:** unchanged; the `.older` rules stay for when the list returns.

## Not changing

- Receipt pages, short links, sitemap, media copying (every receipt's media is already copied for its
  own page), `reel.js`.
- No receipt re-renders.

## Cost of more slides on the root page

Stills are `<img loading="lazy">`; videos are `preload="none"` with no `src` until `reel.js` sets one
when the slide comes on screen. So 8 (or a few dozen) slides add markup, not load-time downloads.

## Checks

`make format`, `uv run pytest`, `make guard`; build the site locally (`cachereg site`) and screenshot the
end of the reel (last slide, its "More", the CTA and footer) in portrait and landscape.
