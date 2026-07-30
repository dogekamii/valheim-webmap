# Dependency provenance

The canonical release builds websocket-sharp from verified source; no repository DLL is accepted as a dependency input.

## Locked source

| Fact | Value |
|---|---|
| Upstream project | [sta/websocket-sharp](https://github.com/sta/websocket-sharp) |
| Immutable commit | `4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1` |
| Source archive | `https://codeload.github.com/sta/websocket-sharp/tar.gz/4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1` |
| Archive SHA-256 | `310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a` |
| License | MIT; complete 2021 notice in `THIRD-PARTY-NOTICES.txt` |
| Project path | `websocket-sharp/websocket-sharp.csproj` |
| Compiler/toolchain | Debian bookworm `mono-devel` / xbuild `6.8.0.105+dfsg-3.3+deb12u1`, pinned in `Dockerfile` |
| Build output | `/tmp/websocket-sharp-build/websocket-sharp.dll` |
| Intermediate output | `/tmp/websocket-sharp-build/obj/` |
| Assembly identity | `websocket-sharp, Version=1.0.2.29017, Culture=neutral, PublicKeyToken=5660b08a1845a91e` |

The canonical image download rejects redirects and non-HTTPS transport, requires HTTP 200 and an expected gzip media type, verifies the exact SHA-256 before extraction, and rejects absolute/parent paths, unexpected roots, links, and device nodes. The archive must contain the signed .NET 3.5 project, key, assembly metadata, and license. Only the upstream wildcard version declaration is normalized from `1.0.2.*` to `1.0.2.29017`, preserving the identity used by the existing WebMap/Valheim Mono deployment while avoiding a time-generated revision.

## Exact build command

`build.cake` cleans `/tmp/websocket-sharp-build`, recreates its output and `obj` directories as the canonical unprivileged build user, and executes this before compiling WebMap:

```text
xbuild "/opt/websocket-sharp-src/websocket-sharp/websocket-sharp.csproj" /target:Rebuild /property:Configuration=Release /property:OutputPath="/tmp/websocket-sharp-build/" /property:BaseIntermediateOutputPath="/tmp/websocket-sharp-build/obj/" /property:IntermediateOutputPath="/tmp/websocket-sharp-build/obj/" /verbosity:minimal
```

The extracted source remains immutable; the canonical build does not chmod/chown it and does not compile it as root. `WebMap.csproj` references only the current source-build output with CopyLocal enabled. The packager and release inspector byte-compare the CopyLocal/package DLL against that output, reject the removed opaque hash `33c2b65512e71a0c05cbe1c2f89343605653e5f7fada91885ba756b12121b244`, verify the assembly name/version/public-key token and strong-name signature, and preserve exactly four package files.

## Reproducibility boundary and artifact reporting

The source archive, source normalization, compiler package, command, project, and assembly identity are locked. Mono xbuild/mcs 6.8 does not expose a supported deterministic compilation option for this .NET 3.5 project, and PE/compiler timestamps prevent a justified claim that independent clean builds are byte-reproducible. The outputs are therefore **not byte-reproducible** under the supported toolchain. The binary hash is intentionally not hard-coded as a reproducible output. After every package, identity, strong-name, and privacy gate passes, authoritative release inspection publishes the exact artifact SHA-256, size, identity, and pinned `mono-devel` toolchain as a GitHub Actions notice. That hash identifies that release artifact without claiming universal binary determinism.
