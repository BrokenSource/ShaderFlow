---
title: Module
icon: octicons/package-16
---

> **Main file: [shaderflow/module.py](https://github.com/BrokenSource/ShaderFlow/blob/main/shaderflow/module.py)**

A [`ShaderModule`](https://github.com/BrokenSource/ShaderFlow/blob/main/shaderflow/module.py) is a common trait for classes acting on a bound [Scene](scene.md) to follow.

- While it may seem weird, the Scene itself _is also a module_, as it follows the same build, setup, update steps on the pipeline (eg. last to update) and is "bound to itself".
- All modules are [attrs](https://pypi.org/project/attrs/) dataclasses for the speed and unserializable nature.

## Abstract Methods

Modules can optionally define a set of methods to run at certain points of a Scene lifecycle. While these are marked as `@abstractmethod`, they are not enforced (no `ABC` inheritance).

!!! warning "Very Important"
    All methods must call the inheritance one if it exists

    ```python
    @define
    class MyScene(ShaderScene):
        def build(self) -> None:
            ShaderScene.build(self)
            # Your code here
    ```

    <small><b>Note:</b> Class.method(self) is preferred over super().method() to avoid mistakes[^super-mro]</small>

[^super-mro]: About `super()` by mcoding: https://www.youtube.com/watch?v=X1PQ7zzltz4

<hr>

### `__attrs_post_init__`

Avoid using this directly and prefer [build](#build), unless for reasons like spawning worker threads.

The default implementation must always be run and is a syntatic sugar for the following:

```python
# Naive approach
class MyScene(ShaderScene):
    def build(self):
        self.camera = ShaderCamera(scene=self)
        self.modules.append(self.camera)
        self.camera.commands()
        self.camera.build()

# Automatically handled
class MyScene(ShaderScene):
    def build(self):
        self.camera = ShaderCamera(scene=self)
```

It also does important [weakref](https://docs.python.org/3/library/weakref.html) management to avoid circular references on `gc.collect()`, ensures the passed `scene=` object is a `ShaderScene` instance, and calls the `self.build()` method.

<hr>

### `build`

-> Only ever called once on creation, similar to `__init__`.

Here, modules shall create auxiliary objects like Textures, Dynamics, set static settings, load shaders, etc. The Scene's OpenGL Context is guaranteed to exist at this point.

```python
class MyScene(ShaderScene):
    def build(self):
        self.shader.fragment = (shaders/"main.frag")
        self.audio = ShaderAudio(scene=self, name="iAudio")
        self.audio.open_recorder()
```

Further or dynamic configuration is done in [setup](#setup).

<hr>

### `setup`

-> Called every time before the main [`update`](#update) event loop.

Whenever the `Scene.main` method is called, `setup` runs just after configuring it with incoming arguments (like time, width, height) for all modules. Command line options were _just set_.

Generally speaking, dynamic configuration should be done here:

```python
class MyScene(ShaderScene):
    def setup(self):
        if self.image.is_empty():
            self.input(image=DEFAULT_IMAGE)
        self.piano.load_midi(self.config.midi)
        self.piano.height = self.config.height
```

<hr>

### `destroy`

-> Cleanup problematic leaky resources

Certain resources like OpenGL Contexts, Audio Recorders, Worker Threads, etc. might not be automatically cleaned up by Python and require explicit handling.

While `__del__` is a terrible liability[^del], when it run it'll calls `destroy()` for you.

[^del]: About `__del__` by mcoding: https://www.youtube.com/watch?v=IFjuQmlwXgU

### `pipeline`

-> Declare or set uniform variables in the shader pipeline.

Similar to [update](#update), but runs at least once before the event loop for shader compilation.

This method must yield ShaderVariable instances that will be injected in shaders code as uniforms, or value to be set on the OpenGL rendering pipeline.

```python
class MyScene(ShaderScene):
    def pipeline(self) -> Iterable[ShaderVariable]:
        yield from ShaderScene.pipeline()
        yield Uniform("i",
```

!!! tip "Small data only"
    For large data throughput, use [Textures](texture.md) instead

<hr>

### `includes`

!!! warning "🚧 To be reworked"

<hr>

### `defines`

!!! warning "🚧 To be reworked"

<hr>

### `update`

-> Called every frame in the main event loop

Certainly the most called method of all, and often the main implementation of a module. Note you can access `self.scene.{dt,time}` etc for state data.

```python
import functools

@define
class Primer(ShaderModule):
    value: bool = False

    def update(self):
        self.prime = is_prime(self.scene.frame)

    def pipeline(self):
        yield Uniform("iPrime", self.value)
```

!!! tip "Optimization is the art of doing nothing"
    Be lazy, avoid doing work as much as possible here - this is _"the main bottleneck"_ of ShaderFlow:

    - Audio DSP only runs on new audio data; Video only writes a new frame when due, etc.

<small><b>Note:</b> Actual shaders are run last, as the pipeline might change in a parent or global module</small>

<hr>

### `handle`

-> Handle custom messages sent with [relay](#relay) from another module.

Lesser common, but important scene events are always sent here, like keyboard, mouse, window events, shader compilation, resizes, etc - check [message.py](https://github.com/BrokenSource/ShaderFlow/blob/main/shaderflow/message.py)

```python
class MyScene(ShaderScene):
    def handle(self, message: ShaderMessage) -> None:
        ShaderScene.handle(self, message)

        if isinstance(message, ShaderMessage.Window.FileDrop):
            self.background.from_image(message.files[0])
```

<hr>

### `duration`

-> Self-reported time for full completion

When `main` is called with `time=None` (default), the Scene determines the total runtime based on the maximum value of all modules' duration. For example, a `ShaderAudio` returns the duration of the input audio file; a `ShaderPiano` the input's Midi file length, etc.

## Fixed Methods

### `relay`

-> Send any input object to all modules's [handle](#handle) method

```python
# Force recompilation
scene.relay(ShaderMessage.Shader.Compile)
```

<hr>

### `commands`

-> Add custom commands to the scene's [cyclopts](https://github.com/BrianPugh/cyclopts) app

```python
from cyclopts import Parameter

@define
class SceneConfig:
    ...

class SceneConfig(BaseModel):
    ...

@define
class MyScene(ShaderScene):
    config: SceneConfig = Factory(SceneConfig)

    def smartset(self, object: Any) -> Any:
        if isinstance(object, SceneConfig):
            self.config = object
        return object

    def seed(self, value: int):
        print(f"Seed: {value}")
        random.seed(value)

    def commands(self):
        self.cli.help = pianola.__about__
        self.cli.version = pianola.__version__
        self.cli.command(self.seed)
        self.cli.command(
            SceneConfig, name="config",
            result_action=self.smartset
        )
```

<hr>

### `find`

-> Find all modules of a certain type in the scene

```python
for module in scene.find(ShaderTexture):
    print(module.name)
```
