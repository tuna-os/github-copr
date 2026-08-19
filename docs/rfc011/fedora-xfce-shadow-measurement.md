# Fedora 44 XFCE shadow measurement

This is RFC 011 Phase 1's first Fedora/XFCE measurement.  It is **shadow
evidence only**: `build-order-xfce-fedora.yml` remains the executed build
order until a candidate is either identical or each difference has a recorded
disposition.

## Command and evidence

```sh
python3 scripts/measure-target-gap.py --target fedora \
  --cache .cache/fedora-shadow-426 \
  --report-json docs/rfc011/fedora-xfce-shadow-gap.json \
  --build-order docs/rfc011/build-order-xfce-fedora.candidate.yml
```

The accompanying report records the measured Fedora 44 primary metadata as
`c48e47563bbf65b996c95caf4a608223f982c314cab637e6ab87dd1df67b9d26` and the
Rawhide reference metadata as
`5e324190028d308360ae94926af5c8824840e9bb1f2fe0124ba25903d269f763`.

## Comparison with the executed order

| Existing package | Candidate result | Disposition |
| --- | --- | --- |
| `xfconf` | already shipped by Fedora 44 | required Fedora 44 version-floor upgrade |
| `libxfce4ui` | already shipped by Fedora 44 | required Fedora 44 version-floor upgrade |
| `xfwl4` | absent from the Rawhide reference index | upstream Rawhide change not valid for the Fedora 44 target |

The zero-tier candidate is not adopted.  The existing order stays
`xfconf → libxfce4ui → xfwl4`: it is backed by the Fedora 44 build proof and
the version floors documented in that manifest.  In particular, absence of
`xfwl4` from a newer Rawhide index is not evidence that Fedora 44 can omit it.

No Fedora fallback is added or broadened by this shadow measurement.
