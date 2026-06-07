# Code Duplication Check

Repository copy/paste detection is provided by `jscpd` and wrapped by the root
script:

```bash
./run-duplication-check.sh
```

The default mode is exploratory. It writes console, JSON, and HTML reports to
`/tmp/jscpd-termin-report-own` and exits with success even when existing
duplication is found.

Install the CLI when it is not already available:

```bash
npm install --global jscpd
```

Useful focused runs:

```bash
./run-duplication-check.sh termin-app termin-base
./run-duplication-check.sh --output /tmp/jscpd-termin-app termin-app
./run-duplication-check.sh --min-lines 12 --min-tokens 120
./run-duplication-check.sh --silent --reporters json,html
```

Use `--threshold` only when the check is meant to act as a quality gate:

```bash
./run-duplication-check.sh --threshold 5
```

By default the script excludes vendored code in `termin-app/third/**` and
`termin-thirdparty/**`. Pass `--include-thirdparty` when auditing external code
layout or pending third-party migrations.

## Initial Baseline

The first first-party run used:

```bash
./run-duplication-check.sh
```

Baseline result from 2026-06-07:

- Sources: 1719
- Lines: 271070
- Clones: 398
- Duplicated lines: 13464
- Duplicated line percentage: 4.97%
- Duplicated token percentage: 6.42%

The largest findings are migration leftovers rather than small local copy/paste:

- duplicated `trent` sources between `termin-base` and `termin-app/cpp`
- duplicated texture and mesh handle implementations between extracted modules
  and `termin-app`
- repeated C++/Python binding blocks

These should be handled as module ownership cleanup. Smaller local clones can be
triaged after the obsolete architectural copies are removed.

## Cleanup Progress

After removing obsolete first-party copies from `termin-app/cpp`, the current
baseline from 2026-06-07 is:

- Sources: 1693
- Lines: 266127
- Clones: 362
- Duplicated lines: 8697
- Duplicated line percentage: 3.27%
- Duplicated token percentage: 4.69%

Removed or redirected so far:

- `termin-app/cpp/trent/**` now comes from `termin-base`
- `termin-app/cpp/termin/texture/tc_texture_handle.*` now comes from
  `termin-graphics`
- `termin-app/cpp/termin/mesh/**` and stale app mesh bindings now come from
  `termin-mesh`
- `termin-app/cpp/termin/render/tc_value_trent.*` now comes from `termin-base`
