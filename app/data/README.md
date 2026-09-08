# Premier League 2024/25 data

`matches.csv` contains 380 completed matches between 20 teams, normalized from
[OpenFootball's England dataset](https://github.com/openfootball/england).
The source is distributed under **CC0 1.0 Universal**; the upstream license is
included in [source/LICENSE.md](source/LICENSE.md). This license applies to the
dataset, and does not establish a license for this project's application code.

## Provenance

- Season: 2024/25, from 2024-08-16 through 2025-05-25.
- Source revision: `0690446f794fde748ea4b994244def699c6a65b2`.
- [Pinned source file](https://github.com/openfootball/england/blob/0690446f794fde748ea4b994244def699c6a65b2/2024-25/1-premierleague.txt).
- Local original: `source/2024-25-premierleague.txt` (upstream bytes preserved).
- Source SHA-256: `e39716b01af0c8654a9fae7b5555e6b02f506ea05239e0d0eef41936ba80e1e3`.
- Normalized CSV SHA-256: `282a2e89e5afa787f314ce21aa45da4ed205de68be3c795316128332b7e65347`.
- Machine-readable provenance: [source/manifest.json](source/manifest.json).

## Reproduce

From the repository root after `make setup`:

```bash
make ingest
```

This reads the included source, verifies its checksum, and regenerates the CSV
without downloading anything. Use `--download` to retrieve and verify the same
pinned revision from upstream, or `--output /tmp/matches.csv` to write elsewhere.

Normalization removes the trailing `FC` from team names, creates ISO dates and
stable date/team IDs, and derives H/D/A from the full-time score. The source omits
half-time scores for 0–0 matches; only those are filled as 0–0 because no goals
were scored. Other missing half-time scores are rejected. Output uses UTF-8,
LF line endings, and date/ID sorting. Validation checks score consistency,
unique IDs, season dates, and one home fixture per ordered pair of teams.

## Query semantics

- Win/draw/loss and half-time outcome are from the requested team's perspective.
- Average goals means goals **scored by the team** per selected match.
- Every tool returns `value`, contributing match IDs as `evidence`, and normalized
  arguments in `query_metadata`. A zero count has an empty evidence list.
- Known aliases are explicit in `app/football/normalizer.py`. Following the POC
  plan, bare “United” means Manchester United; this is a project convention,
  not a generally unambiguous football name. Unknown names fail validation.
- Comparison questions will compose multiple tools in the analyst layer.
- Half-time/full-time filters are supported by `count_team_matches`.

This snapshot has match results, not player statistics, injuries, transfers,
formations, or live information. The independent synthetic test fixture checks
calculation behavior separately from the real dataset.
