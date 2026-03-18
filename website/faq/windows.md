---
title: Windows
icon: material/microsoft
---

-> **Note**: For executables see [Pyaket's FAQ](https://pyaket.dev/faq/windows/)

### **Q:** Wrong GPU being used {#wrong-gpu}

Hybrid systems might offload lightweight tasks to the weaker or integrated gpu for performance, battery life, and efficiency reasons. Since ShaderFlow is a _'generic'_ Python application that simply uses [moderngl](https://github.com/moderngl/moderngl) contexts, the operating system is being lazy (in a good way) with its choice.

Using the integrated card in a hybrid system can cause crashes or poor performance.

=== ":simple-nvidia: Nvidia"
    > - Open the Nvidia Control Panel, go to _Manage 3D settings_ and either:
    >     1. Find the Python interpreter or project executable being run
    >     2. Go for the _Global Settings_ tab (discouraged)
    > - Set the preferred graphics to the Nvidia GPU, apply settings.
=== ":simple-amd: AMD"
    > Unknown, consider improving this answer if you have one!
=== ":simple-intel: Intel"
    > Unknown, consider improving this answer if you have one!

On every scene initialization, it prints the renderer in use, a good output is eg.:

```
$ shaderflow basic main
│0'00.936├┤info │ Initializing scene Basic with backend WindowBackend.GLFW
│0'01.186├┤info │ OpenGL Renderer: NVIDIA GeForce RTX 3060/PCIe/SSE2
...
```

### **Q:** Artifacts in uint16 textures {#amd-u16}

Seems to only happen in AMD cards, setting `texture.anisotropy = 1` fixes it.

<small><b>Related:</b> [DepthFlow#83](https://github.com/BrokenSource/DepthFlow/issues/83) • [DepthFlow#84](https://github.com/BrokenSource/DepthFlow/issues/84)</small>
