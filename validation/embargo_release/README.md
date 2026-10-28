# Controlled validation of embargo release

This package records a controlled test executed on the development host on 2026-10-28. It is evidence for release-date routing, not an observed production release event.

## Reproduce

Use a Python environment with GAVO DaCHS (`gavo`), NumPy, and Astropy installed. From this directory run:

```sh
python3 test_release.py zeroed_service.rd > results_local.json
```

Do not run Python with `-O`: the test uses assertions. Exit status 0 and four `passed: true` cases indicate success. A failed assertion terminates execution with a nonzero status. The script executes the supplied RD code, so only use trusted descriptors.

`zeroed_service.rd` is the exact service element extracted from the tested full RD; it is a test fixture, not a complete deployable archive configuration. Both executable code blocks are unchanged. `provenance.json` records hashes of the full original RD and the extracted fixture. `results_development.json` contains the original execution results with only the absolute source path removed. Its RD hash refers to the full original descriptor. New execution times and the fixture hash will differ from that record.

## Method and results

The deployed setup and core code execute with a controlled clock and database test double. The database double always returns the same synthetic product and release date (2026-10-29). The source FITS has two image HDUs with nonzero int16 and float32 arrays.

| Simulated date | Expected and observed output |
| --- | --- |
| 2026-10-28 | Both arrays zero-valued |
| 2026-10-29 | Byte-identical original FITS |
| 2026-10-30 | Byte-identical original FITS |
| 2026-10-28, repeated | Masked output reproduced |

All four cases passed. Header blocks remained byte-identical, output length was preserved, and the source file remained unchanged. Synthetic files are temporary and removed automatically. No actual observation files, database rows, server clocks, or service settings are modified.

Two separate live HTTP regression checks also passed on the development service: SIAP metadata discovery and masked delivery of an embargoed image. This initial package records that observation but does not include the original raw HTTP-test log or real observation fixture. The four controlled cases above are the independently reproducible evidence in this package.

## Limits

The test does not exercise actual database lookup, ingestion, or an HTTP request spanning the real release boundary. It does not validate all FITS encodings (for example scaled unsigned data or compressed images), all failure paths, or long-term operation. The implementation uses the server's local calendar date via `datetime.date.today()`; a UTC boundary is not established by this test.

## Publication contents

Only synthetic test data definitions, generic service code, hashes, and test results are included. Archive paths, real target identifiers, credentials, connection settings, and the rest of the deployment descriptor are omitted. The generic schema and product-prefix names are retained because they are part of the tested code.
