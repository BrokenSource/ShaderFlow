---
icon: material/file-document-edit
---

### ✏️ v0.10.0 <small>September ??, 2025</small> {#0.10.0}

!!! example ""
    - Recalled all executable releases, enough users didn't see warnings
    - Fixed FFmpeg command line interface options missing
    - Minor tweaks to `Scene.main` typer arguments
    - Fix `turbopipe.sync` shouldn't be called when disabled

### 📦 v0.9.0 <small>June 2, 2025</small> {#0.9.0}

!!! success ""
    - Add an heuristic to use the headless context when exporting videos
    - Fix progress bar creation before ffmpeg command log causing a bad line
    - Fix frametimer first frame being `dt=0` instead of `1/fps`
    - Rename `ShaderObject` to `ShaderProgram` to better reflect ModernGL
    - Initial ground work on better metaprogramming and include system
    - Partial overhaul and simplify the `ShaderTexture` class
    - `ShaderTexture.track` is now a float ratio of the scene's resolution
    - Drastically improve import times and consequently CLI startup times
    - Speed improvements with float64 on dynamic number and optional aux vars
    - [**(#61)**](https://github.com/BrokenSource/DepthFlow/issues/61)  Fix many _(skill issue)_ memory leaks:
        - Use `#!py weakref.proxy()` on every module's `.scene` to allow for deeper `gc.collect()` to find circular references and clean up resources properly
        - Release proxy render buffers that are piped to ffmpeg when done
        - Release texture objects when ShaderTexture is garbage collected
        - Do not recreate imgui context on every scene init
    - Base duration of the scenes are now configurable (10 seconds default)
    - Throw an exception when FFmpeg process stops unexpectedly
    - Fix sharing a global watchdog causing errors on many initializations
    - Cleanup scheduler before module setup, fixes scene reutilization bug
    - Add a new 'subsample' parameter for better downsampling of SSAA>2
    - Use macros for initializing structs with fixed specification from uniforms
    - Bundle the `Examples` directory into `Resources` for wheel releases
    - Support for rendering videos "in-memory" without a named file on disk
    - Refactor `ExportingHelper` out of `ShaderScene.main`
    - Properly catch FFmpeg's `stderr` and `stdout` (allows in-memory render)
    - Convert the project into snake case, still have my differences

### 📦 v0.8.0 <small>October 27, 2024</small> {#0.8.0}

!!! success ""
    - [**(#6)**](https://github.com/BrokenSource/ShaderFlow/issues/6) Move away from [pyimgui](https://pypi.org/project/imgui/) to [imgui-bundle](https://pypi.org/project/imgui-bundle/)
    - Fix `Scene.tau` overlooked calculation, it was _half right!_
    - Add optional frameskipping disabling on `Scene.main`
    - Add optional progress callback on `Scene.main`
    - The `Camera.zoom` is now the distance from the center to the top
    - Add `Camera.fov` bound to `Camera.zoom`, a simple tan atan relation
    - Use `numpy.dtype` instead of spaghetti methods on `Texture`
    - Add many `Scene.log_*` methods for DRY 'who module's logging
    - Do not fit rendering resolutions every frame (slow)
    - Add a `Uniform` class for convenience than the whole `Variable`
    - Fix bug ensure the parent directory exists when exporting
    - Revert `vflip`'s duty to FFmpeg than on the final sampling shader
    - Renamed `Scene.main(benchmark=)` to `freewheel` (exporting mode)
    - Internal code simplification and bug fixes
