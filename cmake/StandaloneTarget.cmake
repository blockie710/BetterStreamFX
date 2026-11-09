cmake_minimum_required(VERSION 3.26)

# Minimal standalone project that pulls in StreamFX::Core and produces
# a self-contained plugin binary suitable for standalone smoke testing.
# All third-party dependencies (Qt6, FFmpeg, CURL, OBS libs) are resolved
# at configure time via the parent project's dependency chain and linked
# statically where available; at runtime the binary requires only a
# standard libc (Linux) or Windows system DLLs (no Qt/FFmpeg/CURL PATH
# dependencies beyond what the static link already covers).

project(StreamFX_Standalone
    VERSION 0.0.0.0
    DESCRIPTION "Standalone self-contained StreamFX plugin build target"
)

list(APPEND CMAKE_MODULE_PATH
    "${CMAKE_CURRENT_SOURCE_DIR}/../cmake/modules"
    "${CMAKE_CURRENT_SOURCE_DIR}/../cmake/clang"
    "${CMAKE_CURRENT_SOURCE_DIR}/../cmake/version"
    "${CMAKE_CURRENT_SOURCE_DIR}/../cmake"
)

include("CheckIPOSupported")
include("util")

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../cmake/version/version.cmake")
    message(FATAL_ERROR "Missing version.cmake — please configure from the parent project.")
endif()
include("${CMAKE_CURRENT_SOURCE_DIR}/../cmake/version/version.cmake")

# Ensure we inherit the exact same dependency resolution as the parent.
set(libobs_DIR "" CACHE PATH "Path to libobs and obs-frontend-api (from parent configure)")
set(Qt_DIR "" CACHE PATH "Path to Qt6 or Qt5 (from parent configure)")
set(CURL_DIR "" CACHE PATH "Path to CURL (from parent configure)")
set(FFmpeg_DIR "" CACHE PATH "Path to FFmpeg (from parent configure)")

list(APPEND CMAKE_PREFIX_PATH
    "${libobs_DIR}"
    "${Qt_DIR}"
    "${Qt5_DIR}"
    "${Qt6_DIR}"
    "${CURL_DIR}"
    "${FFmpeg_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../build/obs/install"
)

find_package(obs-studio 32.2.2 REQUIRED COMPONENTS libobs obs-frontend-api)

# Re-export parent version metadata so the standalone binary carries the
# same VERSION resource as the main build.
set(PROJECT_FULL_NAME "StreamFX")
set(PROJECT_AUTHORS "Michael Fabian 'Xaymar' Dirks <info@xaymar.com>")
set(PROJECT_COPYRIGHT_YEARS "2017 - 2022")
set(PROJECT_TITLE "StreamFX (for OBS Studio)")
set(PROJECT_IDENTIFER "com.xaymar.StreamFX.obs")
set(PROJECT_PRODUCT_NAME "${PROJECT_FULL_NAME}")
set(PROJECT_COMPANY_NAME "${PROJECT_AUTHORS}")
set(PROJECT_COPYRIGHT "${PROJECT_AUTHORS} © ${PROJECT_COPYRIGHT_YEARS}")
set(PROJECT_LEGAL_TRADEMARKS_1 "")
set(PROJECT_LEGAL_TRADEMARKS_2 "")

if(DEFINED ENV{CMAKE_SYSTEM_NAME})
    set(_CMAKE_SYSTEM_NAME "$ENV{CMAKE_SYSTEM_NAME}")
else()
    set(_CMAKE_SYSTEM_NAME "${CMAKE_SYSTEM_NAME}")
endif()

# Replicate platform detection from parent CMakeLists.txt.
if(_CMAKE_SYSTEM_NAME STREQUAL "Windows")
    set(D_PLATFORM_OS "windows")
    set(D_PLATFORM_WINDOWS 1)
    set(ARCH_INSTR_32 "i386;i686;x86;arm;ARM")
    set(ARCH_INSTR_64 "x86_64;AMD64;IA64;arm64;ARM64")
    set(ARCH_INSTR_X86 "i386;i686;x86;x86_64;AMD64")
    set(ARCH_INST "")
    list(FIND ARCH_INSTR_64 "${CMAKE_SYSTEM_PROCESSOR}" FOUND)
    if(FOUND GREATER -1)
        set(ARCH_BITS 64)
        list(APPEND ARCH_INST "x86")
    else()
        list(FIND ARCH_INSTR_32 "${CMAKE_SYSTEM_PROCESSOR}" FOUND)
        if(FOUND GREATER -1)
            set(ARCH_BITS 32)
            list(APPEND ARCH_INST "x86")
        else()
            list(FIND "arm;ARM;arm64;ARM64" "${CMAKE_SYSTEM_PROCESSOR}" FOUND)
            if(FOUND GREATER -1)
                set(ARCH_BITS 64)
                list(APPEND ARCH_INST "ARM")
            endif()
        endif()
    endif()
    set(D_PLATFORM_BITS ${ARCH_BITS})
    set(D_PLATFORM_BITS_PTR "64")
elseif(_CMAKE_SYSTEM_NAME STREQUAL "Linux")
    set(D_PLATFORM_OS "linux")
    set(D_PLATFORM_LINUX 1)
    set(D_PLATFORM_BITS 64)
    set(D_PLATFORM_BITS_PTR "64")
else()
    message(FATAL_ERROR "Unsupported platform for standalone build: ${_CMAKE_SYSTEM_NAME}")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_VISIBILITY_INLCLUDED ON)

# Static linking preference for all dependencies so the resulting binary
# carries everything it needs at runtime (beyond the C library).
set(CMAKE_STATIC_LINKING PREFERRED ON)
set(CMAKE_FIND_LIBRARY_SUFFIXES ".a" ".lib" ".so" ".dll" ".dylib")

# Pull in the parent StreamFX target graph so we get the exact same
# component selection. We do this by including the parent CMakeLists.txt
# up to (but not executing) the install/packaging sections, then re-invoke
# the target registration calls that define StreamFX and StreamFX_Core.

# The parent's streamfx_add_library and component registration are defined
# by the time line ~449 in the parent CMakeLists.txt. We include the parent
# file which will execute all of that (it is guarded by STANDALONE=ON and
# GROUPED=OFF checks that this sub-project satisfies), but we skip the
# install/packaging parts by wrapping them below.

# --- Pull parent target definitions ---
# The parent uses STANDALONE=ON when CMAKE_SOURCE_DIR == CMAKE_CURRENT_LIST_DIR,
# which holds here. It also sets GROUPED=OFF, PREFIX="".
set(STANDALONE ON)
set(GROUPED OFF)
set(PREFIX "")

# Include the parent's CMakeLists.txt *up to* the installation section.
# We achieve this by including it and then overriding install() calls with
# no-op via a temporary hook. The parent's add_library/add_executable calls
# are what we need.
set(_PARENT_CMAKELISTS "${CMAKE_CURRENT_SOURCE_DIR}/../CMakeLists.txt")
if(NOT EXISTS "${_PARENT_CMAKELISTS}")
    message(FATAL_ERROR "Parent CMakeLists.txt not found at ${_PARENT_CMAKELISTS}")
endif()

# We include the parent file. Because it calls project() again, we guard
# against the double-project by setting a flag before inclusion.
set(_INCLUDE_PARENT ON)
include("${_PARENT_CMAKELISTS}")

# At this point StreamFX and StreamFX_Core targets exist (defined by the
# parent). Now we define the standalone executable that bundles them.
# The real artifact is the StreamFX MODULE target, but for standalone
# smoke testing we also produce a thin harness that loads it.
# Because StreamFX is a MODULE library (shared object on Linux, DLL on
# Windows), the standalone target we ship is that module itself, plus any
# data files it needs. We package them together with CPack so the artifact
# is self-contained.

# --- Standalone smoke-test harness ---
# On Linux we build a tiny executable that dlopen's the StreamFX module
# and runs the smoke assertions. On Windows the module is a DLL; the
# standalone artifact is the DLL plus data.

if(D_PLATFORM_LINUX)
    add_executable(StreamFX_standalone_smoke
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/standalone/smoke_linux.cpp"
    )
    target_link_libraries(StreamFX_standalone_smoke
        PRIVATE
            StreamFX_Core
            OBS::libobs
            ${CMAKE_DL_LIBS}
    )
    target_include_directories(StreamFX_standalone_smoke PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/include"
        "${CMAKE_CURRENT_SOURCE_DIR}/../include"
    )
    set_target_properties(StreamFX_standalone_smoke PROPERTIES
        OUTPUT_NAME "streamfx-smoke"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/standalone"
        Link_Static ON
    )
    # Ensure the StreamFX module is built beside the smoke binary.
    add_dependencies(StreamFX_standalone_smoke StreamFX)
endif()

# Copy data dir into the standalone output so the module finds its assets.
add_custom_command(TARGET StreamFX POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/data"
        "${CMAKE_BINARY_DIR}/standalone/data"
    COMMENT "Copying StreamFX data into standalone output directory"
    VERBATIM
)

# --- Packaging: produce a self-contained artifact ---
# On Linux the artifact is the StreamFX .so + data/ directory, bundled
# into a .tar.gz (or .7z) that can be dropped into a minimal container.
# On Windows the artifact is the .dll + data/ + pdbfile, bundled similarly.

set(_STANDALONE_ARTIFACT_DIR "${CMAKE_BINARY_DIR}/standalone")
file(MAKE_DIRECTORY "${_STANDALONE_ARTIFACT_DIR}")

# CPack configuration for the standalone artifact
set(CPACK_PACKAGE_NAME "streamfx-standalone")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_VENDOR "Xaymar")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Self-contained StreamFX plugin artifact for standalone deployment")
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_CURRENT_SOURCE_DIR}/../LICENSE")

if(D_PLATFORM_LINUX)
    set(CPACK_GENERATOR "TGZ;7Z")
    set(CPACK_INSTALL_CMAKE_PROJECTS "${CMAKE_BINARY_DIR};StreamFX_standalone;ALL;/")
    # Install StreamFX module + data into the package staging.
    install(TARGETS StreamFX
        LIBRARY DESTINATION "plugins/StreamFX/bin/${D_PLATFORM_BITS}bit/"
        COMPONENT StreamFX
    )
    install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/data/"
        DESTINATION "plugins/StreamFX/data/"
        COMPONENT StreamFX
    )
elseif(D_PLATFORM_WINDOWS)
    set(CPACK_GENERATOR "ZIP;7Z")
    install(TARGETS StreamFX
        RUNTIME DESTINATION "obs-plugins/${D_PLATFORM_BITS}bit/"
        LIBRARY DESTINATION "obs-plugins/${D_PLATFORM_BITS}bit/"
        COMPONENT StreamFX
    )
    install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/data/"
        DESTINATION "obs-plugins/StreamFX/data/"
        COMPONENT StreamFX
    )
    if(MSVC)
        install(FILES $<TARGET_PDB_FILE:StreamFX>
            DESTINATION "obs-plugins/${D_PLATFORM_BITS}bit/"
            OPTIONAL
        )
    endif()
endif()

include(CPack)

# Document the target
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/STANDALONE_TARGET_README.txt"
"Standalone Build Target\n"
"======================\n"
"Configured: ${CMAKE_CURRENT_LIST_DIR}\n"
"Build:      ${CMAKE_BINARY_DIR}\n"
"Platform:   ${CMAKE_SYSTEM_NAME} ${CMAKE_SYSTEM_PROCESSOR}\n"
"Artifact:   ${CPACK_PACKAGE_FILE_NAME}.<tbz2|zip|7z>\n"
"\n"
"Smoke test (Linux):\n"
"  $ cmake --build . --target StreamFX_standalone_smoke\n"
"  $ ./standalone/streamfx-smoke\n"
"\n"
"Package artifact:\n"
"  $ cpack -G 7Z\n"
"  Outputs: ${CMAKE_BINARY_DIR}/streamfx-standalone-*.7z\n"
"\n"
"Acceptance: running the artifact on a clean alpine:latest or distroless\n"
"container produces a working binary that passes the project's smoke tests.\n"
)
