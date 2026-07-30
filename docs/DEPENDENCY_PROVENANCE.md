# Dependency provenance

Release dependencies are measured from repository content, not inferred from filenames or licence prose.

| Binary filename | Assembly version | Size (bytes) | SHA-256 | Repository Git blob SHA | First repository import | Upstream project | Licence / notice source |
|---|---:|---:|---|---|---|---|---|
| `websocket-sharp.dll` | `1.0.2.29017` | `254464` | `33c2b65512e71a0c05cbe1c2f89343605653e5f7fada91885ba756b12121b244` | `140cbc4f926d622ec913791d319b7fb99f5d7e58` | commit `5e5c3361fdac8926f62349bb352cd95c8951f1e9`, Kyle Paulsen, 2021-04-09 | [sta/websocket-sharp](https://github.com/sta/websocket-sharp) | MIT; 2021 notice at commit [`4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1`](https://github.com/sta/websocket-sharp/blob/4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1/LICENSE.txt) |

## Provenance boundary

The binary has remained unchanged from its first import in this repository, as identified by the same Git blob SHA. Repository history does not record the upstream websocket-sharp source revision, build command, compiler, or build environment that produced it. **Exact binary-to-source-build provenance remains unverified.** The 2021 upstream commit above is the source of the applicable MIT notice; this document does not claim the bundled binary was built from that commit.

The canonical release build independently verifies the repository binary and packaged copy against the size and SHA-256 above. `THIRD-PARTY-NOTICES.txt` carries the complete notice in every release package.
