---
title: General
icon: octicons/package-16
---

-> **Note**: For executables see [Pyaket's FAQ](https://pyaket.dev/faq/general/)

## **Q:** Crashes on exporting videos {#export-crashes}

-> Using `scene main --no-turbo (...)` or `scene.main(turbo=False)` might fix it.

ShaderFlow uses an auxiliary library called [TurboPipe](https://github.com/BrokenSource/TurboPipe) (from the same author) to speed up data transfers to FFmpeg (video encoder) by offloading it to a fast, multithreaded C++ code.

While no known pattern has been found on _why_ it happens, it is believed to be related with hybrid systems _or_ the lack of driver support for the CPU to directly read from a [mapped buffer](https://github.com/moderngl/moderngl/blob/97107741e58fb037fe8a1ba0007210bf87657593/src/moderngl.cpp#L1399-L1430); perhaps even a bug in TurboPipe itself with lifetimes and garbage collection. Please ensure the package is using the right primary gpu, as muxing/ownership can cause issues too.

However, the vast majority of systems have no issues with it, so it's currently opt-out.

<small><b>Note:</b> Disabling turbopipe can make exporting up to 50% slower if you've got the cpu headroom for it.</small>

## **Q:** Only pixel shaders? {#pixel-shaders}

ShaderFlow _does not aim_ to support vertex data or complex OpenGL features, only but one thing and doing it well: Rendering a fullscreen rectangle with a pixel shader, similar to shadertoy.

This is _**not** a limitation_, nor implies 3D scenes aren't possible - in fact, they tend to look much better and interesting than traditional rasterization by using [Ray Marching](https://en.wikipedia.org/wiki/Ray_marching) techniques.

-> For a practical example, check out the [⭐️ DepthFlow](https://github.com/BrokenSource/DepthFlow) project!

<small><b>Note:</b> For such work, you're better off using [Blender](https://www.blender.org/) or [Godot](https://godotengine.org/), which are Open Source and awesome!</small>

## **Q:** Extension GL_* is required {#missing-extension}

Not all drivers and hardware are made equal - depending on your functions and features used, particular combinations of software and hardware might not support the shader altogether.

A practical example is a function that returns a `sampler2D`:

```glsl
// Metaprogrammed to get the nth layer from uniforms
sampler2D iScreenGet(int layer) {
    if (layer == 0) return iScreen0;
    if (layer == 1) return iScreen1;
    if (layer == 2) return iScreen2;
    if (layer == 3) return iScreen3;
    return iScreen0; // Fallback
}
```

This function fails for Windows AMD GPU with `GL_ARB_bindless_texture is required` and macOS; adding a request for it fixes for Windows but is completely unsupported in macOS.

A workaround for this example case is to rethink the function:

```glsl
vec4 iScreenGet(int layer, vec2 uv) {
    if (layer == 0) return texture(iScreen0, uv);
    if (layer == 1) return texture(iScreen1, uv);
    if (layer == 2) return texture(iScreen2, uv);
    if (layer == 3) return texture(iScreen3, uv);
    return texture(iScreen0, uv);
}
```
