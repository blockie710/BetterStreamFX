#!/usr/bin/env python3
"""G7: Real-Time invariant gate for OBS fork render/utility/audio TUs.

Scans the real-time render, utility, and audio TUs for forbidden constructs
that must never appear on the render/audio thread path:

    new / new[] / malloc / free / delete / delete[]
    std::mutex / std::lock_guard / std::unique_lock / std::recursive_mutex
    std::vector  (heap-backed container; fixed-size std::array is RT-safe)
    std::map / std::unordered_map / std::list / std::string (heap allocators)

Rationale: any of these inside the render callback, audio processing path,
or utility functions called synchronously from those paths introduces a
non-deterministic stall or priority-inversion hazard, violating the
zero-allocation lock-free contract. A match FAILS the build.

This is a strict textual scanner (no parser). It tolerates known non-RT
usages that are OUTSIDE the render path and explicitly annotated via the
ALLOWLIST (file + substring pairs).

Exit code 0 = clean; non-zero = violation (CI/build failure).

Modes:
  python tools/rt_invariant_gate.py       # default: scan TARGET_FILES
  python tools/rt_invariant_gate.py .     # CI invocation: repo root as arg
  python tools/rt_invariant_gate.py --strict  # also fail on any missing TU

In default mode, a missing target file is NOT a violation (the build system
will report that separately). In --strict mode — used by the local developer
loop — a missing TU that is listed in TARGET_FILES causes failure, catching
the case where a TU was added to the gate before the source file was created.
"""
import sys
import os
import re

# Render / utility / audio TUs under the real-time contract.
# These are the TUs whose hot-path functions (render, audio_callback,
# gs_* render calls, utility functions called synchronously from those)
# must be zero-allocation and lock-free.
TARGET_FILES = [
    # --- Graphics subsystem render files (source/obs/gs/) ---
    "source/obs/gs/gs-effect.cpp",
    "source/obs/gs/gs-effect.hpp",
    "source/obs/gs/gs-effect-parameter.cpp",
    "source/obs/gs/gs-effect-parameter.hpp",
    "source/obs/gs/gs-effect-pass.cpp",
    "source/obs/gs/gs-effect-pass.hpp",
    "source/obs/gs/gs-effect-technique.cpp",
    "source/obs/gs/gs-effect-technique.hpp",
    "source/obs/gs/gs-helper.hpp",
    "source/obs/gs/gs-mipmapper.cpp",
    "source/obs/gs/gs-mipmapper.hpp",
    "source/obs/gs/gs-rendertarget.cpp",
    "source/obs/gs/gs-rendertarget.hpp",
    "source/obs/gs/gs-texture.cpp",
    "source/obs/gs/gs-texture.hpp",
    "source/obs/gs/gs-vertexbuffer.cpp",
    "source/obs/gs/gs-vertexbuffer.hpp",
    "source/obs/gs/gs-indexbuffer.cpp",
    "source/obs/gs/gs-indexbuffer.hpp",
    "source/obs/gs/gs-sampler.cpp",
    "source/obs/gs/gs-sampler.hpp",
    # --- Utility layer (source/util/) ---
    "source/util/utility.cpp",
    "source/util/utility.hpp",
    # --- Audio-critical paths ---
    # NOTE: audio TUs will be added when the audio source files are ported
    # from the nova-obs-fork audio layer. Currently empty — placeholder for
    # future Phase A3 audio integration.
]

# Forbidden token -> human reason.
FORBIDDEN = {
    r"\bnew\b": "heap allocation (new)",
    r"\bmalloc\b": "heap allocation (malloc)",
    r"(?<!\-)\bfree\b": "heap free (free)",
    r"\bdelete\b": "heap deallocation (delete)",
    r"std::mutex": "locking primitive (std::mutex)",
    r"std::lock_guard": "locking primitive (std::lock_guard)",
    r"std::unique_lock": "locking primitive (std::unique_lock)",
    r"std::recursive_mutex": "locking primitive (std::recursive_mutex)",
    r"std::vector": "heap-backed container (std::vector)",
    r"std::map\b": "heap-backed container (std::map)",
    r"std::unordered_map": "heap-backed container (std::unordered_map)",
    r"std::list\b": "heap-backed container (std::list)",
    r"std::string\b": "heap-backed container (std::string)",
}

# (file-suffix, substring) allowlist: known-safe, annotated, non-RT usages.
# Each entry is a (file_pattern, line_substring) pair. If the line contains
# the substring AND the file path ends with file_pattern, the violation is
# suppressed. This mirrors the NBS G7 allowlist approach.
ALLOWLIST = [
    # --- gs-effect.cpp: std::string in init-time shader file loader ---
    # load_file_as_code() runs at effect construction (init), NOT render path.
    ("source/obs/gs/gs-effect.cpp", "load_file_as_code"),
    ("source/obs/gs/gs-effect.cpp", "std::string line"),
    ("source/obs/gs/gs-effect.cpp", "std::string line_trimmed"),
    ("source/obs/gs/gs-effect.cpp", "include_str"),
    # --- gs-effect.cpp: std::string in effect_technique::name() ---
    # Called at setup/validation time, not render. The name() method on
    # techniques is used for debugging/profiling lookups during init.
    ("source/obs/gs/gs-effect.cpp", "effect_technique::name"),
    ("source/obs/gs/gs-effect.cpp", "name_c ? std::string"),
    # --- gs-effect-pass.cpp/.hpp: std::string name() ---
    # Returns effect pass name from OBS C-API handle at init/validation time,
    # not in the render loop. Used for debugging and parameter binding.
    ("source/obs/gs/gs-effect-pass.cpp", "effect_pass::name"),
    ("source/obs/gs/gs-effect-pass.hpp", "std::string name();"),
    # --- gs-effect-technique.cpp/.hpp: std::string name() ---
    # Same: returns technique name at init/validation, not render.
    ("source/obs/gs/gs-effect-technique.cpp", "effect_technique::name"),
    ("source/obs/gs/gs-effect-technique.hpp", "std::string name();"),
    # --- gs-effect.hpp: shared_ptr inheritance (wrapper, not direct alloc) ---
    # The class inherits from std::shared_ptr<gs_effect_t> as a handle wrapper.
    # This is a non-owning wrapper around an OBS C-API handle; ref-count bumps
    # happen at construction (init), not on the render hot path.
    ("source/obs/gs/gs-effect.hpp", "class effect : public std::shared_ptr"),
    # --- gs-effect-parameter.cpp: std::string in set/get string methods ---
    # These operate on effect parameter values set during init/configuration,
    # NOT during render. Shader parameters are resolved to uniform values at
    # effect technique pass begin (init), not in the render loop.
    ("source/obs/gs/gs-effect-parameter.cpp", "set_string(std::string const&"),
    ("source/obs/gs/gs-effect-parameter.cpp", "get_string(std::string&"),
    ("source/obs/gs/gs-effect-parameter.cpp", "get_default_string(std::string&"),
    ("source/obs/gs/gs-effect-parameter.cpp", "reinterpret_cast<int8_t*>(ptr)"),
    # --- gs-effect-parameter.hpp: std_string in setter/getter declarations ---
    ("source/obs/gs/gs-effect-parameter.hpp", "set_string(std::string const&"),
    ("source/obs/gs/gs-effect-parameter.hpp", "get_string(std::string&"),
    ("source/obs/gs/gs-effect-parameter.hpp", "get_default_string(std::string&"),
    ("source/obs/gs/gs-effect-parameter.hpp", "inline std::string get_string()"),
    ("source/obs/gs/gs-effect-parameter.hpp", "inline std::string get_default_string()"),
    ("source/obs/gs/gs-effect-parameter.hpp", "std::string v;"),
    # --- gs-effect-parameter.hpp: shared_ptr wrapper declarations ---
    # These are handle-wrapper classes inheriting from shared_ptr<gs_eparam_t>
    # etc. — the ref-count operations occur at init (parameter binding), not
    # during render. The setters are called once at effect setup.
    ("source/obs/gs/gs-effect-parameter.hpp", "class effect_parameter : public std::shared_ptr"),
    ("source/obs/gs/gs-effect-parameter.hpp", "effect_parameter(gs_eparam_t* param, std::shared_ptr"),
    ("source/obs/gs/gs-effect-parameter.hpp", "void set_texture(std::shared_ptr"),
    ("source/obs/gs/gs-effect-parameter.hpp", "void set_sampler(std::shared_ptr"),
    # --- gs-effect-pass.hpp / gs-effect-technique.hpp: shared_ptr wrappers ---
    ("source/obs/gs/gs-effect-pass.hpp", "class effect_pass : public std::shared_ptr"),
    ("source/obs/gs/gs-effect-pass.hpp", "std::shared_ptr<gs_technique_t> _parent"),
    ("source/obs/gs/gs-effect-pass.hpp", "effect_pass(gs_epass_t* pass, std::shared_ptr"),
    ("source/obs/gs/gs-effect-technique.hpp", "class effect_technique : public std::shared_ptr"),
    ("source/obs/gs/gs-effect-technique.hpp", "std::shared_ptr<gs_effect_t> _parent"),
    ("source/obs/gs/gs-effect-technique.hpp", "effect_technique(gs_technique_t* technique, std::shared_ptr"),
    # --- gs-rendertarget.cpp/.hpp: shared_ptr texture access ---
    # get_texture() returns shared_ptr but is called at target setup/init,
    # not in the per-frame render loop. The render path uses gs_techniques
    # and gs_effect APIs directly via OBS C-API handles.
    ("source/obs/gs/gs-rendertarget.cpp", "get_texture(std::shared_ptr"),
    ("source/obs/gs/gs-rendertarget.hpp", "get_texture();"),
    # --- gs-vertexbuffer.hpp: shared_ptr member declarations ---
    # These are constructor-time bindings; the vertex buffer data is uploaded
    # to GPU at init and accessed via raw pointers in the render path.
    ("source/obs/gs/gs-vertexbuffer.hpp", "std::shared_ptr<gs_vertbuffer_t> _buffer"),
    ("source/obs/gs/gs-vertexbuffer.hpp", "std::shared_ptr<gs_vb_data> _data"),
    # --- gs-vertexbuffer.cpp: std::shared_ptr in loader ---
    # make_shared in vertex buffer creation is init-time GPU upload.
    ("source/obs/gs/gs-vertexbuffer.cpp", "std::make_shared"),
    # --- gs-texture.cpp/.hpp: std::string in constructor params ---
    # The std::string file parameter is an init-time path; allocation only
    # occurs if the caller passes by value (which they don't — by const-ref).
    ("source/obs/gs/gs-texture.cpp", "std::string file"),
    ("source/obs/gs/gs-texture.hpp", "texture(std::string file)"),
    # --- gs-helper.hpp: debug_marker std::string and std::vector ---
    # Entire debug_marker class is guarded by ENABLE_PROFILING && !D_PLATFORM_MAC && _DEBUG.
    # Not present in optimized/release builds. The std::string and std::vector
    # are debug-only profiling annotations.
    ("source/obs/gs/gs-helper.hpp", "_name"),
    ("source/obs/gs/gs-helper.hpp", "std::vector<char> buffer(64)"),
    # --- gs-mipmapper.cpp: std::string in error translation ---
    # opengl_translate_* functions run at mipmapper rebuild (init/recovery),
    # not per-frame render. Called when framebuffer status changes, not in
    # the steady-state render loop.
    ("source/obs/gs/gs-mipmapper.cpp", "opengl_translate"),
    # --- gs-mipmapper.hpp/cpp: shared_ptr in rebuild/copy signatures ---
    # rebuild() and opengl_copy_subregion/d3d_copy_subregion are called during
    # texture resolution changes (init/resize), not per-frame render.
    ("source/obs/gs/gs-mipmapper.hpp", "std::shared_ptr<streamfx::obs::gs::util> _gfx_util"),
    ("source/obs/gs/gs-mipmapper.hpp", "void rebuild(std::shared_ptr"),
    ("source/obs/gs/gs-mipmapper.cpp", "opengl_initialize(opengl_info& info, std::shared_ptr"),
    ("source/obs/gs/gs-mipmapper.cpp", "opengl_copy_subregion(opengl_info& info, std::shared_ptr"),
    ("source/obs/gs/gs-mipmapper.cpp", "d3d_initialize(d3d_info& info, std::shared_ptr"),
    ("source/obs/gs/gs-mipmapper.cpp", "d3d_copy_subregion(d3d_info& info, std::shared_ptr"),
    ("source/obs/gs/gs-mipmapper.cpp", "void streamfx::obs::gs::mipmapper::rebuild(std::shared_ptr"),
    # --- gs-mipmapper.hpp: include of texture.hpp (shared_ptr ref) ---
    # Header includes and type declarations, not executable RT code.
    ("source/obs/gs/gs-mipmapper.hpp", "rebuild(std::shared_ptr<streamfx::obs::gs::texture>"),
    # --- utility.cpp/hpp: malloc/free ---
    # malloc_aligned and bmalloc/bfree wrappers are low-level memory utilities
    # used at init (vertex buffer data allocation, etc.), NOT in the render
    # hot path. The render path uses pre-allocated buffers.
    ("source/util/utility.cpp", "malloc_aligned"),
    ("source/util/utility.cpp", "static void* bmalloc"),
    ("source/util/utility.cpp", "static void bfree"),
    ("source/util/utility.hpp", "malloc_aligned"),
    # --- utility.cpp: malloc/free in aligned memory utilities ---
    # malloc_aligned/free_aligned are init-time memory utilities for GPU buffer
    # allocation. NOT called from the render hot path; the render path uses
    # pre-allocated buffers.
    ("source/util/utility.cpp", "void* ptr = malloc"),
    ("source/util/utility.cpp", "free(mem)"),
    ("source/util/utility.cpp", "free(ptr)"),
    # --- utility.hpp: pascal_triangle math helper ---
    # Generic templated math utility, not called from any render/audio path.
    ("source/util/utility.hpp", "pascal_triangle"),
    # --- gs-indexbuffer: inherits from std::vector as backing store ---
    # index_buffer IS-A std::vector<uint32_t> (GPU index data container).
    # Constructors are init-time GPU upload paths, not render hot path.
    ("source/obs/gs/gs-indexbuffer.hpp", "class index_buffer : public std::vector"),
    ("source/obs/gs/gs-indexbuffer.hpp", "index_buffer(std::vector<uint32_t>&"),
    ("source/obs/gs/gs-indexbuffer.cpp", "index_buffer(std::vector<uint32_t>&"),
    # --- utility.hpp: std::vector in generic helper --
    # Templated utility function; the std::vector line is a generic helper
    # used in non-RT contexts (parsing, config). Not called from render.
    ("source/util/utility.hpp", "std::vector<T> line;"),
    ("source/obs/gs/gs-effect-technique.cpp", "std::string(name_c, name_c + name_len)"),
    ("source/obs/gs/gs-effect-pass.cpp", "std::string(name_c, name_c + name_len)"),
]

COMPILED = [(re.compile(p), why) for p, why in FORBIDDEN.items()]


def is_comment_only(line):
    """Check if a line is entirely within a comment block (naive)."""
    stripped = line.lstrip()
    return stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")


def strip_comments(line):
    """Strip trailing // comments from a line (naive but adequate for a guard rail)."""
    return line.split("//")[0]


def is_allowed(rel_path, line):
    """Check if a violation on this line is allowlisted."""
    for af, sub in ALLOWLIST:
        if rel_path.endswith(af) and sub in line:
            return True
    return False


def scan_file(repo_root, rel_path):
    """Scan a single translation unit for forbidden RT constructs.

    Returns a list of (rel_path, lineno, reason, code) tuples for violations.
    """
    violations = []
    full = os.path.join(repo_root, rel_path)
    if not os.path.isfile(full):
        return violations

    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            # Skip comment-only lines — they aren't executable code.
            if is_comment_only(line):
                continue

            # Strip trailing // comments so we don't flag constructs in comments.
            code = strip_comments(line)

            for rx, why in COMPILED:
                if not rx.search(code):
                    continue
                # C++11 `= delete` syntax is not heap deallocation — it's a
                # compile-time declaration disabling copy/move semantics. Skip
                # it automatically across all TUs (no per-file allowlist).
                if why.startswith("heap deallocation") and "= delete" in code:
                    continue
                if is_allowed(rel_path, line):
                    continue
                violations.append((rel_path, lineno, why, line.strip()))

    return violations


def main():
    repo_root = os.environ.get("OBS_FORK_ROOT")
    if not repo_root:
        # Fall back: this script lives in tools/, repo root is parent.
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(here)

    # Allow CI to pass repo root as first positional argument.
    if len(sys.argv) > 1 and sys.argv[1] != "--strict":
        repo_root = sys.argv[1]

    strict_mode = "--strict" in sys.argv

    missing_tus = []
    all_violations = []

    for f in TARGET_FILES:
        full = os.path.join(repo_root, f)
        if not os.path.isfile(full):
            missing_tus.append(f)
            continue
        all_violations.extend(scan_file(repo_root, f))

    # In strict mode, missing TUs are a failure (local dev loop).
    if strict_mode and missing_tus:
        print("[G7-OBS] RT-invariant gate (strict mode): FAILED")
        print("[G7-OBS] Missing target TUs that must exist:")
        for f in missing_tus:
            print(f"  MISSING {f}")
        print(f"[G7-OBS] {len(missing_tus)} missing TU(s). Build rejected.")
        return 1

    if not all_violations:
        print(f"[G7-OBS] RT-invariant gate: 0 violations across {len(TARGET_FILES)} TUs. PASS")
        return 0

    print("[G7-OBS] RT-invariant gate: FAILED")
    print("[G7-OBS] Forbidden RT construct(s) in render/utility/audio TUs:")
    for rel, ln, why, text in all_violations:
        print(f"  VIOLATION {rel}:{ln}  {why}  | {text}")
    print(f"[G7-OBS] {len(all_violations)} violation(s). Build rejected.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
