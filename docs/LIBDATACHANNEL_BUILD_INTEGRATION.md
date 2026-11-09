# libdatachannel Build System Integration Guide

This document captures the research on integrating libdatachannel into the
OBS fork's CMake build system. It answers five concrete questions and
provides ready-to-paste configuration snippets verified against the
upstream source (v0.24.5) and the package managers that ship it.

## Project Context

The OBS fork lives at `C:\Users\bhogl\Projects\nexus-projects\nova-obs-fork`
and already contains:

- `cmake/modules/FindLibDataChannel.cmake` — a custom Find module that
  uses pkg-config as the primary discovery mechanism, with
  `find_path`/`find_library` fallback.
- `CMakeLists.txt` lines 468–487 — the discovery block.
- `CMakeLists.txt` lines 1098–1107 — the conditional link block guarded
  by `TARGET LibDataChannel::LibDataChannel`.
- Downstream consumers include
  `third-party/obs-studio/plugins/obs-webrtc/whip-output.h` which
  `#include`s `<rtc/rtc.hpp>`.

---

## 1. pkg-config vs. CMake config: which is available?

**CMake config files: YES (always provided by upstream).**

libdatachannel's own `CMakeLists.txt` installs a proper CMake package
config at `${CMAKE_INSTALL_LIBDIR}/cmake/LibDataChannel`:

```
LibDataChannelConfig.cmake          (generated from cmake/LibDataChannelConfig.cmake.in)
LibDataChannelConfigVersion.cmake   (write_basic_package_version_file, SameMajorVersion)
LibDataChannelTargets.cmake         (install EXPORT LibDataChannelTargets)
```

The config template is trivial:

```cmake
# cmake/LibDataChannelConfig.cmake.in
@PACKAGE_INIT@
include("${CMAKE_CURRENT_LIST_DIR}/LibDataChannelTargets.cmake")
```

vcpkg's portfile confirms the install layout:

```cmake
# vcpkg portfile.cmake
vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        ${FEATURE_OPTIONS}
        -DPREFER_SYSTEM_LIB=ON
        -DNO_EXAMPLES=ON
        -DNO_TESTS=ON
)
vcpkg_cmake_install()
vcpkg_cmake_config_fixup(CONFIG_PATH lib/cmake/LibDataChannel)
```

**pkg-config: NOT provided by upstream.**

The upstream repository contains **no `.pc.in` template** and **no
`pkg-config` call** in `CMakeLists.txt`. We verified:

- `cmake/libdatachannel.pc.in` returns HTTP 404 from GitHub raw.
- No `pkg_check_modules`, `pkg_config`, or `.pc` generation appears
  anywhere in the CMakeLists.txt.
- The Conan recipe (conan-center-index
  `recipes/libdatachannel/all/conanfile.py`) **deletes** the pkgconfig
  and cmake dirs from the packaged output:
  ```python
  rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
  rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
  ```
  Conan relies on `cpp_info` properties instead:
  ```python
  self.cpp_info.set_property("cmake_file_name", "LibDataChannel")
  self.cpp_info.set_property("cmake_target_name", "LibDataChannel::LibDataChannel")
  ```
- The ConanCenter web listing that reports `libdatachannel.pc` as a pkg-config
  name is **auto-generated metadata** that does not reflect actual upstream
  packaging — it is derived from the Conan recipe's `cmake_file_name` property,
  not from a real `.pc` file on disk.

**Conclusion:** The `.pc.in` file does not exist. The existing
`FindLibDataChannel.cmake` module's `pkg_check_modules(PC_LIBDATACHANNEL
QUIET libdatachannel)` call will silently succeed only when a third-party
pkg-config file exists (e.g., from a distro package or AUR). On a
from-source or vcpkg build, pkg-config will not be found and the module
correctly falls through to `find_path`/`find_library` hints. This is the
intended behavior — the Find module is designed as a fallback wrapper.

---

## 2. Correct package names

### CMake package name and targets

| Provider | CMake package name | Canonical target | Static target |
|---|---|---|---|
| Upstream (from source) | `LibDataChannel` | `LibDataChannel::LibDataChannel` | `LibDataChannel::LibDataChannelStatic` |
| vcpkg | `LibDataChannel` | `LibDataChannel::LibDataChannel` | `LibDataChannel::LibDataChannelStatic` |
| Conan | `LibDataChannel` | `LibDataChannel::LibDataChannel` | — |
| System/distro (pacman) | `LibDataChannel` (via config file) | `LibDataChannel::LibDataChannel` | — |

The target alias is declared in the upstream CMakeLists.txt:

```cmake
# libdatachannel CMakeLists.txt, line 515
set_target_properties(datachannel PROPERTIES EXPORT_NAME LibDataChannel)
add_library(LibDataChannel::LibDataChannel ALIAS datachannel)

set_target_properties(datachannel-static PROPERTIES EXPORT_NAME LibDataChannelStatic)
add_library(LibDataChannel::LibDataChannelStatic ALIAS datachannel-static)
```

### pkg-config name

When a `.pc` file IS available (distro packages only):

```
libdatachannel
```

Verified from ConanCenter listing and the AUR `libdatachannel` package
which installs `libdatachannel.pc`.

---

## 3. Include directories and library names

### Include directory

The public C++ API header lives at:

```
include/rtc/rtc.hpp    (C++ API)
include/rtc/rtc.h      (C API)
```

Upstream sets:

```cmake
target_include_directories(datachannel PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
```

So after installation, the include root is `<prefix>/include` and the
consumer includes with `#include <rtc/rtc.hpp>`.

The OBS fork's `FindLibDataChannel.cmake` searches for the header
`rtc/rtc.hpp` with these hints:

```
ENV LIBDATACHANNEL_PATH
ENV LIBDATACHANNEL_PATH64
${LIBDATACHANNEL_PATH}
${LIBDATACHANNEL_PATH64}
/usr/include
/usr/local/include
/opt/local/include
/sw/include
```
with `PATH_SUFFIXES include`.

### Library name

| Build type | Library name (shared) | Library name (static) |
|---|---|---|
| Linux/macOS | `libdatachannel.so` / `libdatachannel.dylib` | `libdatachannel.a` |
| Windows (MSVC) | `datachannel.lib` (import lib) + `datachannel.dll` (runtime) | `datachannel-static.lib` |
| Conan (MSVC, Debug) | `datachanneld.lib` | `datachannel-staticd.lib` |

The OBS fork's `FindLibDataChannel.cmake` searches for both
`"libdatachannel"` and `"datachannel"` names, and on Windows also locates
the runtime DLL for packaging purposes.

### Compile definitions

When linking the **static** library, define:

```
RTC_STATIC
```

This is set automatically when you link
`LibDataChannel::LibDataChannelStatic`. For the dynamic library no
extra define is needed.

When building libdatachannel itself (not applicable to consumers):

```
RTC_EXPORTS          (when building the library DLL)
```

---

## 4. Platform-specific considerations

### Linux

- **Dependencies (all bundled as submodules by default):**
  - `usrsctp` — SCTP over UDP
  - `plog` — logging
  - `libjuice` — ICE backend (default; `libnice` is the alternative via `USE_NICE`)
  - `libsrtp` — SRTP (only if media support is enabled, i.e. `NOT NO_MEDIA`)
  - `OpenSSL` — TLS backend (default; `USE_GNUTLS` or `USE_MBEDTLS` alternatives)
  - `nlohmann_json` — only for examples/tests

- **System libraries:** `pthread`, `m`, `dl`, `ws2_32` (Windows only)
- **Build flags:** Position-independent code is enabled by default
  (`set(CMAKE_POSITION_INDEPENDENT_CODE ON)`).

**Recommended from-source build:**

```bash
git clone --recurse-submodules https://github.com/paullouisageneau/libdatachannel.git
cd libdatachannel
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DNO_MEDIA=ON \          # omit if you need WebRTC media transport
  -DNO_EXAMPLES=ON \
  -DNO_TESTS=ON \
  -DINSTALL_DEPS_LIBS=OFF
cmake --build build -j$(nproc)
sudo cmake --install build
```

After install, `find_package(LibDataChannel CONFIG)` will succeed
automatically.

### macOS

- Same dependencies as Linux.
- OpenSSL path quirk: CMake's `FindOpenSSL` may pick the system LibreSSL
  instead of Homebrew OpenSSL. Set:
  ```bash
  export OPENSSL_ROOT_DIR="$(brew --prefix openssl@3)"
  ```
- On Apple platforms, `find_package(OpenSSL)` is always used (GnuTLS and
  MbedTLS paths have special macOS handling).
- Xcode project generation is supported:
  ```bash
  cmake -B build -G Xcode -DUSE_GNUTLS=0 -DUSE_NICE=0
  ```

**Universal binary build:**

```bash
cmake -B build \
  -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" \
  -DCMAKE_BUILD_TYPE=Release \
  -DNO_EXAMPLES=ON \
  -DNO_TESTS=ON
```

### Windows

- **Compiler:** MSVC via `NMake Makefiles` or Visual Studio generator.
- **Winsock:** `ws2_32` is linked automatically (`target_link_libraries(datachannel PUBLIC ws2_32)`).
- **DLL distribution:** On Windows, the shared library produces both an
  import library (`datachannel.lib`) and a runtime DLL
  (`datachannel.dll`). The OBS fork's `FindLibDataChannel.cmake`
  includes logic to find the DLL via `find_library(... NAMES ... SUFFIXES .dll ...)`
  so packaging tools can distribute it alongside the plugin.
- **Static linking:** Define `RTC_STATIC` (set automatically via
  `target_compile_definitions(datachannel PUBLIC RTC_STATIC)` when
  building static) and link
  `LibDataChannel::LibDataChannelStatic`.

**Recommended from-source build (MSVC):**

```bat
git clone --recurse-submodules https://github.com/paullouisageneau/libdatachannel.git
cd libdatachannel
cmake -B build -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DNO_EXAMPLES=ON -DNO_TESTS=ON
cd build
nmake
nmake install
```

Or with Visual Studio generator:

```bat
cmake -B build -G "Visual Studio 17 2022" -A x64 -DNO_EXAMPLES=ON -DNO_TESTS=ON
cmake --build build --config Release
cmake --install build --config Release
```

**vcpkg (recommended for Windows):**

```bat
vcpkg install libdatachannel[ws,srtp]:x64-windows
```

The vcpkg features:
- `ws` — WebSocket support (default, corresponds to `NOT NO_WEBSOCKET`)
- `srtp` — media transport support (corresponds to `NOT NO_MEDIA`, pulls in `libsrtp`)
- `stdcall` — C API uses `__stdcall` calling convention

After vcpkg install, integrate with the project's CMake:

```cmake
# Via vcpkg toolchain (recommended)
set(CMAKE_TOOLCHAIN_FILE "${VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake" CACHE STRING "")
find_package(LibDataChannel CONFIG REQUIRED)
target_link_libraries(my_target PRIVATE LibDataChannel::LibDataChannel)
```

---

## 5. Optional dependencies and build options

### libdatachannel compile-time options (affecting the library build)

| Option | Default | Description |
|---|---|---|
| `BUILD_SHARED_LIBS` | `ON` | Build shared library (DLL/shared). OFF = static. |
| `BUILD_SHARED_DEPS_LIBS` | `OFF` | Build submodules (usrsctp, juice, srtp) as shared. |
| `USE_GNUTLS` | `OFF` | Use GnuTLS instead of OpenSSL. |
| `USE_MBEDTLS` | `OFF` | Use Mbed TLS instead of OpenSSL. |
| `USE_NICE` | `OFF` | Use libnice instead of libjuice for ICE. |
| `PREFER_SYSTEM_LIB` | `OFF` | Link against system libs rather than submodules. |
| `USE_SYSTEM_SRTP` | (from PREFER_SYSTEM_LIB) | Use system libsrtp2. |
| `USE_SYSTEM_JUICE` | (from PREFER_SYSTEM_LIB) | Use system libjuice. |
| `USE_SYSTEM_USRSCTP` | (from PREFER_SYSTEM_LIB) | Use system libusrsctp. |
| `USE_SYSTEM_PLOG` | (from PREFER_SYSTEM_LIB) | Use system Plog. |
| `USE_SYSTEM_JSON` | (from PREFER_SYSTEM_LIB) | Use system nlohmann_json. |
| `NO_WEBSOCKET` | `OFF` | Disable WebSocket support. |
| `NO_MEDIA` | `OFF` | Disable media transport (SRTP/RTP). |
| `NO_EXAMPLES` | `OFF` | Skip building examples. |
| `NO_TESTS` | `OFF` | Skip building tests/benchmarks. |
| `WARNINGS_AS_ERRORS` | `OFF` | Treat compiler warnings as errors. |
| `CAPI_STDCALL` | `OFF` | Use `__stdcall` for C API callbacks on Windows. |
| `SCTP_DEBUG` | `OFF` | Enable SCTP debug output. |
| `RTC_UPDATE_VERSION_HEADER` | `OFF` | Regenerate `version.h` at build time. |

### Dependency implications for consumers

When you link against libdatachannel, the following transitive
dependencies are automatically pulled in via the exported
`LibDataChannelTargets.cmake`:

| Dependency | Required? | When needed |
|---|---|---|
| `Threads::Threads` | Always | All builds |
| `Usrsctp::Usrsctp` | Always | Submodule or system |
| `plog::plog` | Always | Submodule or system |
| `libsrtp2` / `srtp2` | Only with media | `NOT NO_MEDIA` |
| `libjuice` / `LibJuice::LibJuice` | Always | ICE backend (or `LibNice::LibNice` if `USE_NICE`) |
| `OpenSSL::SSL` | Only with `USE_GNUTLS=OFF` and `USE_MBEDTLS=OFF` | TLS backend |
| `GnuTLS::GnuTLS` + `Nettle::Nettle` | Only with `USE_GNUTLS=ON` | TLS backend |
| `MbedTLS::MbedTLS` | Only with `USE_MBEDTLS=ON` | TLS backend |
| `ws2_32` | Windows only | Winsock |
| `nlohmann_json` | Only for examples/tests | Not a library dependency |

### Consumer-side compile definitions

If you consume the **static** library, you must define `RTC_STATIC`:

```cmake
# Only needed when linking LibDataChannel::LibDataChannelStatic
target_compile_definitions(my_target PRIVATE RTC_STATIC)
```

WebSocket and media availability are controlled at the library build time:

```cpp
// Check at C++ preprocessor level
#ifdef RTC_ENABLE_WEBSOCKET
#include <rtc/websocket.hpp>
#endif

#ifdef RTC_ENABLE_MEDIA
#include <rtc/track.hpp>
#endif
```

These are always defined by libdatachannel's CMake (`PUBLIC RTC_ENABLE_WEBSOCKET=1`
or `0`, `PUBLIC RTC_ENABLE_MEDIA=1` or `0`).

---

## Integration with the OBS Fork

### Current state (already implemented)

The OBS fork's `CMakeLists.txt` (lines 468–487, 1098–1107) already has
the correct integration pattern:

```cmake
# Discovery (STANDALONE builds only)
if(STANDALONE)
    find_package("LibDataChannel" CONFIG QUIET)
    if(NOT TARGET LibDataChannel::LibDataChannel)
        find_package("LibDataChannel" MODULE QUIET)
    endif()
endif()
if(TARGET LibDataChannel::LibDataChannel)
    set(LIBDATACHANNEL_FOUND ON)
else()
    set(LIBDATACHANNEL_FOUND OFF)
    message(STATUS "libdatachannel was not found; ...")
endif()

# Linking
if(TARGET LibDataChannel::LibDataChannel)
    target_link_libraries(StreamFX_Core PUBLIC LibDataChannel::LibDataChannel)
    target_include_directories(StreamFX_Core PRIVATE ${LIBDATACHANNEL_INCLUDE_DIRS})
    target_compile_definitions(StreamFX_Core PUBLIC HAS_LIBDATACHANNEL)
endif()
```

### Recommendation: Remove the `STANDALONE` guard

The `STANDALONE` guard around `find_package` means libdatachannel is only
searched for in standalone (non-OBS-bundled) builds. If the fork's
CMake also supports building within the OBS Studio source tree, the
discovery should be available unconditionally (with the
`if(TARGET ...)` guard making it safe when the library is absent).

### Recommended pkg-config fallback improvement

The existing `FindLibDataChannel.cmake` already handles the
pkg-config → find_path/find_library fallback chain correctly. No changes
are needed. The `pkg_check_modules(PC_LIBDATACHANNEL QUIET libdatachannel)`
call is harmless when no `.pc` file exists — CMake silently skips it
and proceeds to filesystem hints.

### CMake prefix path wiring

The OBS fork already adds `LIBDATACHANNEL_PATH` to `CMAKE_PREFIX_PATH`
(line 374), so `find_package(LibDataChannel CONFIG)` will find an
installed library without additional configuration.

---

## Quick Start Commands

### Install libdatachannel from source (Linux/macOS)

```bash
git clone --recurse-submodules https://github.com/paullouisageneau/libdatachannel.git
cd libdatachannel
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DNO_EXAMPLES=ON \
  -DNO_TESTS=ON \
  -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build -j$(nproc)
sudo cmake --install build
# Optional: verify pkg-config (if distro .pc installed)
pkg-config --modversion libdatachannel 2>/dev/null || echo "no pkg-config file (expected from source build)"
# Verify CMake config
find /usr/local/lib/cmake/LibDataChannel -type f
# → LibDataChannelConfig.cmake, LibDataChannelConfigVersion.cmake, LibDataChannelTargets.cmake
```

### Install via vcpkg (Windows/Linux/macOS)

```bash
vcpkg install libdatachannel[ws,srtp]:x64-windows
# or for 32-bit:
vcpkg install libdatachannel[ws,srtp]:x86-windows
```

### Install via Conan

```bash
conan install libdatachannel/0.24.5 --build=missing
```

### Consume in CMake

```cmake
# Preferred: config-mode (from source install or vcpkg)
find_package(LibDataChannel CONFIG REQUIRED)
target_link_libraries(my_target PRIVATE LibDataChannel::LibDataChannel)

# Fallback: module mode (uses FindLibDataChannel.cmake)
# find_package(LibDataChannel MODULE REQUIRED)
# target_link_libraries(my_target PRIVATE LibDataChannel::LibDataChannel)
```

### Verify the include path

```bash
# The public header is always at this path:
ls <install-prefix>/include/rtc/rtc.hpp

# C API header:
ls <install-prefix>/include/rtc/rtc.h
```

---

## Summary Table

| Question | Answer |
|---|---|
| 1. pkg-config or CMake config? | CMake config files **only** (no `.pc.in` upstream). pkg-config `.pc` exists only in distro packages (e.g., AUR). |
| 2. pkg-config name / CMake name | pkg-config: `libdatachannel`; CMake package: `LibDataChannel`, target: `LibDataChannel::LibDataChannel` (shared) / `LibDataChannel::LibDataChannelStatic` (static) |
| 3. Include dirs / library | Include: `<prefix>/include` (header at `rtc/rtc.hpp`); Library: `datachannel` (shared) / `datachannel-static` (static); Windows DLL: `datachannel.dll` alongside import lib `datachannel.lib` |
| 4. Platform considerations | Linux: `-fPIC`, pthread/m/dl; macOS: OpenSSL path quirk + universal binary support; Windows: MSVC, ws2_32 linked automatically, DLL packaging needed |
| 5. Optional dependencies | Crypto backend: OpenSSL (default), GnuTLS, MbedTLS; ICE backend: libjuice (default), libnice; Media: libsrtp (disable with `NO_MEDIA`); WebSocket: always on unless `NO_WEBSOCKET` |

---

## Sources

- Upstream CMakeLists.txt: `https://github.com/paullouisageneau/libdatachannel/blob/master/CMakeLists.txt`
- BUILDING.md: `https://github.com/paullouisageneau/libdatachannel/blob/master/BUILDING.md`
- Config template: `cmake/LibDataChannelConfig.cmake.in` (trivial package init include)
- vcpkg port: `ports/libdatachannel/portfile.cmake` + `ports/libdatachannel/vcpkg.json`
- Conan recipe: `conan-io/conan-center-index/recipes/libdatachannel/all/conanfile.py`
- OBS fork: `cmake/modules/FindLibDataChannel.cmake`, `CMakeLists.txt` lines 468–487 and 1098–1107
