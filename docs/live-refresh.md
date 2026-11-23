# On-demand price checks from the phone

An APK is a viewer; it cannot run this Python/Chrome collector on Android. The
private companion in `collector/serve.py` runs on the existing computer. The
configured APK sends **Refresh** requests to it through the phone's authorized
ADB connection. Keep the computer awake, online, and connected to the phone.
This setup works over the current wireless debugging connection and over USB;
it does not provide an internet-hosted collector when away from this computer.

## Operation

```powershell
# Connect the already-paired phone, then start/reuse the companion:
.\start_live.ps1 -Device <adb-device-serial>

# Build the matching private APK (run in app/):
flutter build apk --release --dart-define-from-file=../logs/live_config.json
```

The helper generates `logs/live_config.json` if absent. It contains a random
build-specific bearer token and the localhost addresses. It is ignored by Git;
do not publish it. The installed APK must use the same configuration as the
running companion. No GitHub credentials are placed in the app. The server binds
only to `127.0.0.1`, authenticates all routes, exposes a fixed command and fixed
JSON files, and is reached using `adb reverse`. Android cleartext access is
limited to loopback; store links and other network traffic keep HTTPS defaults.

The server runs as a hidden background process. Restart the helper after rebooting
the computer or reconnecting ADB. The service periodically restores the reverse
port mapping when an authorized ADB transport reconnects. No Windows firewall or
public internet listener is required.

## Refresh behavior

1. Opening the app loads the latest completed snapshot. It also resumes following
   an existing job, including after the app was closed during collection.
2. Tapping Refresh, or pulling to refresh on Overview, sends `POST /api/refresh`.
   It starts one full fresh job, or joins the current job if one is already running.
   Automatic stores are read again, including search pages and each resolved
   variant/seller. Manual social pages remain manual entries.
3. The app polls the job and shows checked/total sources and the current store.
   The user can browse the previous prices while collection continues. Refresh
   buttons are disabled while following a job, with server-side deduplication too.
4. The collector runs in an isolated `logs/refresh-jobs/<id>/data` directory with
   `--fresh`. Earlier daily history and product **URLs** are seeds; no old price or
   stock observation enters the new run. Failed sources therefore cannot silently
   contribute earlier prices to this fresh result.
5. Only a completed run with verified offers is published into `data/` and the
   bundled asset files. The app fetches latest/history together through
   `GET /api/snapshot`, caches the result and shows source success/failure counts.
   A completely failed check preserves the previous completed snapshot and allows
   retry. Some websites can block requests; their failures remain visible.

The existing CLI supports `--fresh` and `--progress-file <path>`. Ordinary scheduled
runs retain their prior same-day retry behavior unless `--fresh` is requested.
Workspace collections use an OS-released SQLite write lock to avoid simultaneous
CLI/scheduled runs writing the same files. Each source retains its existing crawl
limits and partial-coverage warnings. A whole companion job has a one-hour limit.

## Private API and diagnostics

- `GET /api/health`: companion reachability.
- `POST /api/refresh`: start/join, with no request-body commands or source URLs.
- `GET /api/jobs/active`, `GET /api/jobs/<id>`: durable progress/result metadata.
- `GET /api/snapshot`: one consistent latest/history response.
- `GET /data/latest.json`, `GET /data/history.json`: authenticated fixed data routes.

Job logs and atomic progress files are kept in `logs/refresh-jobs/`. Tokens are
never printed in those logs. A companion restart marks interrupted jobs as failed
instead of presenting them as running forever. Standard APK builds without live
configuration retain the published-feed download behavior; custom data folders
also remain download-only.

Collector stdout/stderr use UTF-8 explicitly so Arabic store messages cannot abort
a detached Windows run. For maintenance only, `serve.py --config <private-config>
--resume-job <failed-id>` can finish this same job's checkpoints. It validates the
source IDs and every observation timestamp against the original job start before
reusing them. User-initiated Refresh after a failure starts a new fresh job.

Validation includes Python HTTP integration tests for authentication, duplicate
requests, result publication and failure/retry; Flutter tests cover actual
POST/poll/download ordering, progress, repeated taps, reopening, failure recovery,
and the previous cache/bundle freshness safeguards. Progress layout is checked at
375px, landscape and tablet widths with 2× text and reduced animations.

## Live verification — 15 November 2026

- Release APK **1.0.2 (version code 3)** installed over the existing Samsung app
  through wireless ADB. Its embedded companion configuration was checked against
  the running private service without printing its token.
- The fresh job begun at 13:40 completed at **14:02:48 Cairo time**, including
  maintenance recovery from the Windows log-encoding failure. All observations
  and source-check timestamps were verified to be from that same job.
- Result: **202 offers, 115 marked in stock, 38 successful sources and five errors**
  (Dubai Phone, El Nekhely, Kaafo, Sharaf DG and El Shennawy). No earlier same-day
  observations were retained in this fresh result.
- The phone displayed the updated 44 base Disc offers from 23 stores, then showed
  another fresh job started at **14:03:33**, with source progress and the previous
  completed prices still available. Duplicate API requests were also verified to
  join a running job rather than create a second collector.
- **33 Python tests and 8 Flutter tests pass.** The actual Dart snapshot/statistics
  models parse the final JSON and reproduce its default aggregates. Source JSON
  and bundled files match. Flutter analysis reports four existing style infos;
  the release APK passes Android's build/lint checks.
