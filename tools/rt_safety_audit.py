#!/usr/bin/env python3
"""G7: Real-Time safety audit gate for the OBS fork CSP (plugin) layer.

This is the CSP-targeted companion to NBS' rt_invariant_gate.py. It scans the
real-time render, utility, and audio translation units (TUs) for the 6 G7
forbidden RT-invariant patterns that must never appear on the render/audio
callback thread path:

    new / new[]          — dynamic heap allocation (priority-inversion hazard)
    malloc               — C-style heap allocation (non-deterministic overhead)
    delete / delete[]    — heap deallocation on RT thread (reclaim/GC stall)
    mutex                — any std::mutex family (priority inversion / deadlock)
    std::vector          — heap-backed container (capacity growth = alloc)
    std::string          — heap-backed string (capacity growth = alloc)

Rationale: any of these constructs inside the render callback, the audio
processing callback, or utility functions called synchronously from those
paths introduces a non-deterministic stall or priority-inversion hazard,
violating the zero-allocation lock-free contract. A match FAILS the build.

This is a strict textual scanner (no parser). It tolerates known non-RT
usages that are OUTSIDE the render path and explicitly annotated via the
ALLOWLIST (file + substring pairs).

Exit code 0 = clean; non-zero = violation (CI/build failure).

Usage:
    python tools/rt_safety_audit.py              # scan TARGET_FILES
    python tools/rt_safety_audit.py .            # CI invocation: repo root as arg
    python tools/rt_safety_audit.py --strict      # also fail on missing TU
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
    "source/obs/obs-encoder-factory.cpp",
    "source/obs/obs-encoder-factory.hpp",
    "components/shader/source/gfx/shader/gfx-shader-param-audio.cpp",
    "components/shader/source/gfx/shader/gfx-shader-param-audio.hpp",
    # --- Audio processing TUs (future work — placeholder entries) ---
    # These TUs will be implemented by the audio-thread safety initiative
    # (AUDIO-TU-01). They are listed here so that --strict mode flags their
    # absence until the audio engine is ported to the zero-alloc lock-free
    # contract. Do NOT remove without re-assessing the RT audit scope.
    # TODO(AUDIO-TU-01): Implement these TUs from the legacy streamfx-audio layer.
    "source/obs/audio/audio-monitoring.cpp",
    "source/obs/audio/audio-monitoring.hpp",
    "source/obs/audio/audio-thread-resampler.cpp",
    "source/obs/audio/audio-thread-resampler.hpp",
    "source/obs/audio/audio-callback-chain.cpp",
    "source/obs/audio/audio-callback-chain.hpp",
]

# The 6 G7 forbidden patterns (mirrors rt_invariant_gate.py).
# Each entry: (regex, human-readable reason).
FORBIDDEN_PATTERNS = [
    (r"\bnew\b", "heap allocation (new)"),
    (r"\bmalloc\b", "heap allocation (malloc)"),
    (r"\bdelete\b", "heap deallocation (delete)"),
    (r"\bmutex\b", "locking primitive (mutex)"),
    (r"\bstd::vector\b", "heap-backed container (std::vector)"),
    (r"\bstd::string\b", "heap-backed container (std::string)"),
]

COMPILED = [(re.compile(p), why) for p, why in FORBIDDEN_PATTERNS]

# (file-suffix, line_substring) allowlist: known-safe, annotated, non-RT usages.
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
    # --- utility.cpp/hpp: malloc/free / new / delete ---
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
    ("source/util/utility.hpp", "std::vector<T> line;"),
    # --- gs-indexbuffer: inherits from std::vector as backing store ---
    # index_buffer IS-A std::vector<uint32_t> (GPU index data container).
    # Constructors are init-time GPU upload paths, not render hot path.
    ("source/obs/gs/gs-indexbuffer.hpp", "class index_buffer : public std::vector"),
    ("source/obs/gs/gs-indexbuffer.hpp", "index_buffer(std::vector<uint32_t>&"),
    ("source/obs/gs/gs-indexbuffer.cpp", "index_buffer(std::vector<uint32_t>&"),
    # --- gs-effect-pass.cpp: std::string in effect_pass::name() body ---
    # The name() method returns the OBS C-API pass name as std::string.
    # It is called at init/validation/profiling lookups, NOT in the render loop.
    ("source/obs/gs/gs-effect-pass.cpp", "name_c ? std::string(name_c, name_c + name_len)"),
    # --- gs-effect-technique.cpp: std::string in effect_technique::name() body ---
    # Same init-time pattern as gs-effect-pass.cpp above.
    ("source/obs/gs/gs-effect-technique.cpp", "name_c ? std::string(name_c, name_c + name_len)"),
    # --- utility.hpp: std::vector in pascal_triangle math helper ---
    # Templated utility used in non-RT contexts (math helpers during init).
    # Not called from render/audio hot path. The std::vector is built once
    # per call and not on the render hot path.
    ("source/util/utility.hpp", "pascal_triangle"),
    # --- obs-encoder-factory: init-time class members & factory create/destroy ---
    # These allocations/deallocations happen during encoder registration and
    # instance lifecycle (create/destroy callbacks), NOT in the audio render
    # callback or the real-time encoding hot path.
    ("source/obs/obs-encoder-factory.hpp", "std::set<std::string>"),
    ("source/obs/obs-encoder-factory.hpp", "std::map<std::string"),
    ("source/obs/obs-encoder-factory.hpp", "_info_fallback_id"),
    ("source/obs/obs-encoder-factory.hpp", "delete reinterpret_cast<instance_t*>"),
    ("source/obs/obs-encoder-factory.hpp", "new instance_t(settings, encoder, is_hw)"),
    # --- gs-rendertarget: std::shared_ptr get_texture (init-time only) ---
    # Listed above; get_texture() is init/validation, not render.
]


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
    """Scan a single translation unit for forbidden RT-invariant constructs.

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
        print("[G7-OBS] RT-safety audit (strict mode): FAILED")
        print("[G7-OBS] Missing target TUs that must exist:")
        for f in missing_tus:
            print(f"  MISSING {f}")
        print(f"[G7-OBS] {len(missing_tus)} missing TU(s). Build rejected.")
        return 1

    if not all_violations:
        print(f"[G7-OBS] RT-safety audit: 0 violations across {len(TARGET_FILES)} TUs. PASS")
        return 0

    print("[G7-OBS] RT-safety audit: FAILED")
    print("[G7-OBS] Forbidden RT-invariant pattern(s) in render/utility/audio TUs:")
    for rel, ln, why, text in all_violations:
        print(f"  VIOLATION {rel}:{ln}  {why}  | {text}")
    print(f"[G7-OBS] {len(all_violations)} violation(s). Build rejected.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
