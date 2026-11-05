# Result-screen API contracts (W32-W40)

The frontend feature folders below are built against these shapes, defined in
each folder's `types.ts` (the source of truth; this file is the index). All
endpoints are under `/api/v3`, use the same auth bearer token and error
envelope as the Robustness Lab (`{"error": {"message", "details": {"errors": []}}}`),
and use camelCase JSON. A value that could not be computed is `null`, never `0`.
A 404 on a GET is shown as "not available yet".

| Feature (folder)                                | Request                                                                                                                         | Response type       |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| "A beats B" (`comparison/`)                     | `GET /experiments/{id}/comparison?a=&b=&metric=` (all optional)                                                                 | `ComparisonResult`  |
| Sensitivity (`sensitivity/`)                    | `GET /experiments/{id}/sensitivity?metric=`                                                                                     | `SensitivityResult` |
| Delay, travel time, safety, emissions (`kpis/`) | `GET /runs/{runId}/metrics`                                                                                                     | `RunMetrics`        |
| Compare two runs (`runcompare/`)                | `GET /runs/compare?a={runId}&b={runId}`                                                                                         | `RunDiff`           |
| Nightly regression (`regression/`)              | `GET /regression/nightly?limit=30` (newest first)                                                                               | `NightlyRegression` |
| Report (`reports/`)                             | `GET /experiments/{id}/report`                                                                                                  | `ReportDocument`    |
| RL vs fixed-time (`rlcompare/`)                 | `GET /rl/comparisons/{id}`                                                                                                      | `RlComparison`      |
| Network file check (`network/`)                 | `POST /networks/validate`, `multipart/form-data` with `file` and `format` (`auto`, `osm`, `sumo`, `geojson`, `gtfs`, `synchro`) | `ValidationResult`  |
| Road import preview (`network/`)                | `POST /networks/import/preview`, JSON `ImportPreviewRequest`                                                                    | `ImportPreview`     |

## Rules the screens rely on

- **Statistics come from the server.** The UI never computes an interval, p-value
  or verdict. `ComparisonResult.verdict` and `RlComparison.verdict` are the
  server's call; `meanDifference` is the mean of (A minus B) per pair and `ci`
  its interval at `confidenceLevel` (0.95 = 95%).
- **Metric direction.** Every metric carries `lowerIsBetter` (comparison, run
  diff, RL) so the UI can say "lower" or "higher" and colour a change.
- **Method is named.** `ComparisonResult.method` has `test`, `interval` and
  `pairing` strings that are shown verbatim.
- **Eligibility labels** (`eligible` / `indicative` / `exploratory`) are kept from
  the Robustness Lab.
- **Safety and emissions are labelled by the UI** as a proxy and a model
  estimate; the server supplies `definition`, `model.name` and optional `notes`.
- **Sensitivity** `firstOrder` and `total` are fractions 0 to 1; `ci` applies to
  `firstOrder`. `method.seed` makes the ranking reproducible.
- **Nightly regression.** `status` of a night is `pass`, `fail` (a check outside
  tolerance) or `error` (the night could not run). Checks give `expected`,
  `actual`, `tolerance` for numeric failures.
- **Report** is data only; the browser prints it (`window.print()`, "Save as
  PDF"). `assumptions` and `limitations` are shown first. `summary.grounded` is
  true only when the server's number-check passed. A section the server did not
  compute is `null` and is left out.
- **Network validation.** The server answers `200` with `valid: false` and a
  message list for an unusable file; `4xx` (413 too large, 415 unsupported
  type) uses the error envelope. Messages have `severity` (`error`, `warning`,
  `info`), a stable `code`, a plain-language `message`, and optional `line`,
  `element` and `hint`. The client also refuses empty files and files over 50 MB
  before upload.
- **Road import preview.** Send either `place` or `bbox` (`[west, south, east,
north]` degrees), plus `roadClasses`. `links[].geometry` is `[lon, lat]`
  points; `stats.linksShown` may be less than `stats.links` when the server
  thins a large area.

## Wiring

One routed page, `/app/insights` (`src/insights/InsightsPage.tsx`), hosts all
screens as tabs (`?tab=results|runs|nightly|report|rl|network`, plus `experiment`,
`run`, `rl`, `a`, `b` ids). It is registered in `routing.ts` (`VIEW_ROUTES`),
`templates/default.conf.template` (SPA fallback list), `components/shell/sections.ts`
(Experiments section) and `App.tsx` (lazy route). The components are also
exported individually, so they can be dropped into the existing results page:
`ComparisonBlock`, `SensitivityChart`, `RunMetricsSection`, `ReportView`, and
others.
