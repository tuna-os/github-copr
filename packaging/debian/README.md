# Debian and Ubuntu packaging

DEB packages are built from maintained `debian/` directories and published as
signed APT repositories under the `apt/ubuntu/` and `apt/debian/` R2 namespaces
declared in `manifests/package-factory.yaml`.

Do not add a PPA to a TunaOS image. Import the source/package metadata here,
record its provenance in `packages/<name>/source.yaml`, and rebuild it in CI.
