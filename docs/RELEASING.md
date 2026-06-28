# Releasing

Tagged releases are built by .github/workflows/release.yml.

## Prepare

1. Ensure the version in pyproject.toml and CITATION.cff matches the intended tag.
2. Move relevant CHANGELOG.md entries from Unreleased into a dated version section.
3. Run:

~~~bash
make quality
bash -n install.sh ai-factory.sh run.sh scripts/build_binary.sh scripts/render_demo.sh
make media
make build
dist/ai-factory --help
~~~

4. Commit the release preparation.

## Publish

~~~bash
VERSION=v0.3.0
git tag -a "$VERSION" -m "AI Software Factory ${VERSION#v}"
git push origin main
git push origin "$VERSION"
~~~

The release workflow builds native archives for:

- Linux x86_64;
- macOS x86_64;
- macOS arm64;
- Windows x86_64.

It uploads checksums and generates GitHub release notes. Verify every artifact before
announcing the release.

## Rollback

Do not silently replace published artifacts. If a release is broken, document the
problem, publish a patch release, and mark the affected GitHub release as superseded.
