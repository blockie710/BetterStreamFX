# Standalone Build Target

StreamFX can be built as a self-contained artifact that bundles all runtime
dependencies statically (where available) or alongside the binary, requiring
no external runtime beyond a standard C library on Linux or the Windows system
DLLs on Windows.

This target is intended for:

- Distributing StreamFX as an offline-capable plugin package.
- Running smoke tests in minimal containers (alpine:latest, distroless) as
  part of CI.
- Embedding StreamFX into environments where a full OBS Studio installation is
  not present.

## Prerequisites

A standalone build requires a pre-configured dependency tree. The recommended
approach is to first run a normal (bundled) configure, then reuse the resolved
dependency paths for the standalone build:

```bash
# 1. Normal configure (resolves Qt, FFmpeg, CURL, OBS libs, ...)
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON

# 2. Standalone build reuses the same dependency paths.
cmake -S cmake/StandaloneTarget.cmake -B build/standalone \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON \
  -Dlibobs_DIR="$PWD/build/obs/install" \
  -DQt6_DIR="$PWD/build/qt" \
  -DFFmpeg_DIR="$PWD/build/obsdeps" \
  -DCURL_DIR="$PWD/build/obsdeps"
```

On Linux, a fully static build additionally requires static versions of the
dependencies:

```bash
# Debian/Ubuntu example (static libs may need extra packages)
sudo apt-get install \
  libavcodec-dev libavdevice-dev libavfilter-dev libavformat-dev \
  libavutil-dev libswresample-dev libswscale-dev \
  libcurl4-openssl-dev \
  qt6-base-dev qt6-base-private-dev libqt6svg6-dev \
  libx264-dev
```

Static linking of Qt is platform-specific and not always feasible; when static
Qt is unavailable, the build falls back to bundling the shared libraries into
the artifact directory. See `StandaloneTarget.cmake` for the exact behavior.

## Building the Standalone Artifact

From the project root:

```bash
cmake --build build/standalone --target all
cmake --build build/standalone --target package
```

The produced package (`streamfx-standalone-<version>.<ext>`) contains:

- `plugins/StreamFX/bin/<bits>bit/StreamFX.<so/dll>` — the plugin binary.
- `plugins/StreamFX/data/` — runtime data (shaders, effects, assets).
- On Windows, the PDB file is included when built with MSVC.

## Smoke Test (Linux)

The standalone artifact includes a smoke test that verifies the StreamFX
module can be loaded in isolation (without a full OBS runtime present). The
smoke binary is built as part of the standalone target:

```bash
cmake --build build/standalone --target StreamFX_standalone_smoke
./build/standalone/streamfx-smoke \
  ./build/standalone/plugins/StreamFX/bin/64bit/StreamFX.so
```

Exit code 0 indicates the module loaded successfully and exported the expected
OBS plugin contract (obs_module_load / obs_module_unload, plus at least one
plugin registration symbol).

To run the smoke test inside a minimal container:

```bash
# Build the artifact on a full dev system first, then copy to the container.
docker run --rm -v "$PWD/build/standalone:/artifact" \
  alpine:latest \
  /bin/sh -c "apk add --no-cache libstdc++ && \
             /artifact/streamfx-smoke /artifact/plugins/StreamFX/bin/64bit/StreamFX.so"
```

On distroless images, the smoke binary must be compiled with a sufficiently old
glibc (or musl) to match the runtime. See `REPRODUCIBLE_BUILDS.md` for the
verified toolchain matrix.

## Windows Notes

On Windows the standalone artifact is a ZIP (or 7z) containing the StreamFX DLL,
its data directory, and (when built with MSVC) the PDB file. The DLL requires
the Visual C++ Redistributable and any system DLLs that are not statically linked.
The smoke test for Windows is not yet implemented; manual validation is required
when the first Windows standalone package is produced.

## Static Linking Limitations

- **Qt**: Static Qt builds are possible but require a fully static Qt toolchain
  and are not enabled by default. When Qt is dynamically linked, its shared
  libraries are bundled into the package directory alongside the plugin.
- **FFmpeg**: When available as static archives (.a/.lib), FFmpeg is linked
  statically. Otherwise the shared libraries are bundled.
- **CURL**: Same as FFmpeg — static when available, bundled otherwise.
- **OBS lib**: The `libobs` and `obs-frontend-api` libraries are linked against
  the plugin as provided by the dependency tree. A fully static OBS build is not
  part of this target's scope.

## Reproducibility

The standalone build inherits the same determinism guarantees (or lack thereof)
as the parent build. See `REPRODUCIBLE_BUILDS.md` for the documented toolchain
versions, environment variables, and the `reproducible-build` CI job that
asserts hash equality across independent builds.
