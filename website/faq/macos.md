---
title: macOS
icon: simple/apple
---

-> **Note**: For executables see [Pyaket's FAQ](https://pyaket.dev/faq/macos/)

!!! warning "Help me with apple hardware"
    I don't have access to any macOS machine to ensure things work properly for such large userbase, and I can't afford to buy one given the _lack of sustainability_ of Open Source in general.

    -> [Support](https://github.com/sponsors/Tremeschin) my work or donate a used device for development!

## **Q:** Artifacts, black screens {#driver-support}

Apple seems to be a bit iffy on supporting OpenGL at all, so a couple of common mistakes developers make aren't catched and automagically fixed by the driver.

### Unreachable code

For example, the following code shows a white screen and keeps executing past the `return` statement into unreachable code, though using `discard` works normally:

```glsl
void main() {
    if (true) {
        fragColor = vec4(0.5);
        return;
    }
    fragColor = vec4(1.0);
}
```

### Uninitialized memory

Artifacts are often caused by bad memory initialization; the code below should run without issues on any amd, intel, nvidia system in windows or linux, but fail in macOS:

```glsl
void main() {
    fragColor.rgb += vec3(1, 0, 0);
    fragColor.a = 1.0;
}
```

Reason being the `fragColor` variable isn't initialized to `vec4(0)`, a fix is to do it explicitly:

```glsl
void main() {
    fragColor = vec4(0);
    fragColor.rgb += vec3(1, 0, 0);
    fragColor.a = 1.0;
}
```

### Texture indices

Apparently, no `texture()` method works if the bindings aren't contiguous - that is, (0, 1, 2, 3...)

The ShaderTexture and ShaderProgram modules already handles this internally, but whether you're extending or using other ModernGL features, it's worth a check for the case.

