FROM mcr.microsoft.com/dotnet/sdk:8.0 AS dotnet-base

ENV DEBIAN_NONINTERACTIVE=1
ENV PATH="$PATH:~/.dotnet/tools:/opt/steam"
ENV LANG="C.UTF-8"
ENV TZ="Etc/UTC"
ENV DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENV DOTNET_NOLOGO=1

SHELL ["/bin/bash", "-exu", "-o", "pipefail", "-c"]

RUN <<EOF
passwd -d root

cat <<EOD >/etc/apt/apt.conf.d/docker-clean
APT::Install-Recommends "0";
APT::Install-Suggests "0";
Acquire::Retries "5";
Dpkg::Use-Pty "0";
Dpkg::Progress-Fancy "0";
Binary::apt::APT::Keep-Downloaded-Packages "true";
APT::Keep-Downloaded-Packages "true";
EOD

EOF

FROM dotnet-base AS dotnet

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -q && \
    apt-get install -qy npm webpack unzip vim-tiny lib32gcc-s1 util-linux dumb-init && \
    find /var/log -name '*.log' -delete

# 6.0 runtime is currently required for BepInEx Assembly Publicizer Cli
RUN /usr/lib/apt/apt-helper download-file https://dot.net/v1/dotnet-install.sh /usr/local/bin/dotnet-install.sh && \
    chmod +x /usr/local/bin/dotnet-install.sh && \
    dotnet-install.sh -c 6.0 -i /usr/share/dotnet --runtime dotnet && \
    dotnet workload update

ARG BEPINEX_RELEASE
FROM dotnet AS steam

RUN <<EOF
groupadd -g 500 steam
useradd -m -d /opt/steam -u 500 -g 500 steam
passwd -d steam >/dev/null
EOF

USER steam
WORKDIR /opt/steam

RUN <<EOF
curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" | tar zxvf -
ln -s ~/steamcmd.sh ~/steamcmd
steamcmd +login anonymous +quit
EOF

FROM steam AS game

RUN <<EOF
steamcmd +force_install_dir "/opt/steam/valheim" +login anonymous +app_update 896660 +quit
EOF

FROM dotnet AS build

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -q && \
    apt-get install -qy \
      ca-certificates curl python3-minimal \
      mono-devel=6.8.0.105+dfsg-3.3+deb12u1 \
      mono-utils=6.8.0.105+dfsg-3.3+deb12u1 && \
    find /var/log -name '*.log' -delete

ENV WEBSOCKET_SHARP_COMMIT="4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1"
ENV WEBSOCKET_SHARP_ARCHIVE_URL="https://codeload.github.com/sta/websocket-sharp/tar.gz/4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1"
ENV WEBSOCKET_SHARP_ARCHIVE_SHA256="310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a"

# Acquire only the immutable, hash-locked upstream source in the canonical build
# image. Redirects, unexpected media types, unsafe archive members, and hash
# mismatches all fail before extraction. Normalize only the wildcard revision to
# preserve the historical signed assembly identity deterministically.
RUN <<'EOF'
archive="$(mktemp)"
headers="$(mktemp)"
trap 'rm -f "$archive" "$headers"' EXIT
curl --fail --silent --show-error \
  --proto '=https' --tlsv1.2 --max-redirs 0 \
  --header 'Accept: application/x-gzip' \
  --dump-header "$headers" --output "$archive" \
  "$WEBSOCKET_SHARP_ARCHIVE_URL"
status="$(awk '$1 ~ /^HTTP\// { code=$2 } END { print code }' "$headers")"
[[ "$status" == "200" ]]
grep -Eiq '^content-type:[[:space:]]*(application/x-gzip|application/gzip|application/octet-stream)([[:space:]]*;|[[:space:]]*$)' "$headers"
printf '%s  %s\n' "$WEBSOCKET_SHARP_ARCHIVE_SHA256" "$archive" | sha256sum --check --strict -
python3 - "$archive" "$WEBSOCKET_SHARP_COMMIT" <<'PY'
import posixpath
import sys
import tarfile

archive, commit = sys.argv[1:]
expected_root = f"websocket-sharp-{commit}"
with tarfile.open(archive, mode="r:gz") as source:
    members = source.getmembers()
    for member in members:
        normalized = posixpath.normpath(member.name)
        if member.name.startswith("/") or normalized == ".." or normalized.startswith("../"):
            raise SystemExit(f"unsafe archive path: {member.name}")
        if normalized != expected_root and not normalized.startswith(expected_root + "/"):
            raise SystemExit(f"unexpected archive root: {member.name}")
        if member.issym() or member.islnk() or member.isdev():
            raise SystemExit(f"unsafe archive member type: {member.name}")
    required = {
        f"{expected_root}/LICENSE.txt",
        f"{expected_root}/websocket-sharp/websocket-sharp.csproj",
        f"{expected_root}/websocket-sharp/AssemblyInfo.cs",
        f"{expected_root}/websocket-sharp/websocket-sharp.snk",
    }
    names = {member.name for member in members if member.isfile()}
    missing = required - names
    if missing:
        raise SystemExit(f"archive missing required source files: {sorted(missing)}")
PY
mkdir -p /opt/websocket-sharp-src
tar --extract --gzip --file "$archive" --directory /opt/websocket-sharp-src \
  --strip-components=1 --no-same-owner --no-same-permissions
printf '%s\n' "$WEBSOCKET_SHARP_COMMIT" > /opt/websocket-sharp-src/.upstream-commit
assembly_info=/opt/websocket-sharp-src/websocket-sharp/AssemblyInfo.cs
[[ "$(grep -Fxc '[assembly: AssemblyVersion("1.0.2.*")]' "$assembly_info")" == "1" ]]
sed -i 's/AssemblyVersion("1\.0\.2\.\*")/AssemblyVersion("1.0.2.29017")/' "$assembly_info"
grep -Fqx '[assembly: AssemblyVersion("1.0.2.29017")]' "$assembly_info"
test -f /opt/websocket-sharp-src/websocket-sharp/websocket-sharp.csproj
EOF

RUN <<EOF
/usr/lib/apt/apt-helper download-file https://github.com/BepInEx/BepInEx/releases/download/v${BEPINEX_RELEASE}/BepInEx_win_x64_${BEPINEX_RELEASE}.zip bepinex.zip
unzip bepinex.zip BepInEx/*
mv BepInEx /usr/local/share/BepInEx-${BEPINEX_RELEASE}
ln -s /usr/local/share/BepInEx-${BEPINEX_RELEASE} /opt/BepInEx
rm bepinex.zip
EOF

COPY --from=game /opt/steam/valheim/valheim_server_Data/Managed /opt/steam/libs

USER root
WORKDIR /build

RUN chmod a+rx /root

COPY entrypoint.sh /.entrypoint.sh

# Supplying /bin/bash makes canonical build.sh invocation independent of its host mode.
ENTRYPOINT ["/.entrypoint.sh", "/bin/bash"]
