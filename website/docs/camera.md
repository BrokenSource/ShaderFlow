---
title: Camera
icon: octicons/device-camera-video-16
---

> **Main file: [shaderflow/camera.py](https://github.com/BrokenSource/ShaderFlow/blob/main/shaderflow/camera.py)**

ShaderFlow provides a flexible camera system with multiple modes, projections, and parameters already built-in so you can focus on shaders content instead of figuring out vectors math. The main design goals is for a set of parameters usable both in ray marching and 2D shaders.

**Note**: For this page ensure you have a good understanding of the linked [resources](#resources).

## Adding to a Scene

-> All scenes already initializes a default `ShaderCamera` instance at `self.camera`, named `iCamera`!

For adding your own module:

```python
class MyScene(ShaderScene):
    def build(self):
        self.bird = ShaderCamera(scene=self, name="iBird")
```

And then use in shaders:

```glsl
void main() {
    GetCamera(iBird);
    vec2 stuv = iBird.stuv;
    vec2 gluv = iBird.gluv;
}
```

## Coordinates

-> ShaderFlow follows a *Y-Up, Left Handed* euclidean coordinate system.

This choice makes mappings between the 2d screen projection plane (Z=1) and ray-marching vectors 1:1 in xy, which are used in `texture()` sampling methods to avoid weird swizzling.

However, since the camera is generic, you can simply reorient it and work your math in whatever basis you prefer, they don't even need to be euclidean!

## Rotations

-> ShaderFlow uses _Quaternions_ for all rotations.

**Simply stated**, there are no gimbal locks, singularities, or weird edge cases to worry about. While internal logic uses them, there are helper methods simplifying their usage:

```python
# Look at the top of the screen
scene.camera.look((0, 1, 0))

# Clockwise rotation on the screen plane
scene.camera.rotate2d(45)
```

For lower level control or alignment with certain planes:

> _Imagine a screwdriver glued to the camera performing the rotation you want._

The rotation direction is the vector pointing along its tip, and if you'd be tighening the screw the angle is positive, negative otherwise. For example, with your head right now:

- Looking 'left' is a 90° rotation on the 'up' axis direction (earth horizon plane)
- Looking 'down' is a 90° rotation on the 'left' axis direction (vertical nose plane)

```python
# Look at current-left
self.camera.rotate(
    direction=self.camera.up,
    degrees=90.0
)

# Rotate as if to align two vectors
self.camera.align(
    A=(1, 0, 0),
    B=(0, 1, 0),
    degrees=0.0,
)

# Align camera with a custom plane
# Rotate as if to align two vectors
self.camera.align(
    A=self.camera.up_target,
    B=(1, 1, 0),
    degrees=90.0,
)
```

Note that rotations are cumulative and non-commutative, operation orders matter.

<small><b>Note: https://github.com/moble/quaternion/wiki/Euler-angles-are-horrible</b></small>

## Projections

### Parameters

Todo

### Ray Marching

-> Simply use `vec3 iCamera.origin` and `vec3 iCamera.target` in shaders!

### Flat Projection

-> Intersection of the [Ray Marching](#ray-marching) vectors with the `z=1` plane

## Modes

### Free Camera

-> When you are rotating objects in games

In this mode, the camera does absolutely no corrections each update. Moving the mouse always applies a local rotation; eg. when looking down, a 'right' rotation doesn't spin around the center of the screen, but will eventually look at the sky. A non-commutativity side effect is that circular motions _drifts_ the up direction - there are no [zenith](https://en.wikipedia.org/wiki/Zenith) reference anymore.

Movement <kbd>W</kbd> walks in the _forward_ (entering) the screen.

### Camera 2D

In this mode

Movement <kbd>W</kbd> walks in the _up_ screen direction

### Aligned Camera

-> Standard games camera you are used to

In this mode, the right (and consequently, left) axis are always contained in the ground plane, defined by the [zenith](https://en.wikipedia.org/wiki/Zenith) vector. Internally, the camera applies corrections each update.

## Controls

| Key | Action |
| --- | --- |
| <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> | Move |
| <kbd>Q</kbd> <kbd>E</kbd> | Roll |
| <kbd>Space</kbd> <kbd>Shift</kbd> | Move Up/Down |
| <kbd>Mouse</kbd> | Look Around |
| <kbd>1</kbd> | Set mode Free Camera |
| <kbd>2</kbd> | Set mode Camera 2D |
| <kbd>3</kbd> | Set mode Aligned Camera |
| <kbd>i</kbd> <kbd>j</kbd> <kbd>k</kbd> | Set UP Axis (x, y, z) |
| <kbd>Mouse Wheel</kbd> | Change FOV |
| <kbd>T</kbd> <kbd>G</kbd> | Isometric +/- |
| <kbd>F1</kbd> | Exclusive Mouse Mode |

## Resources

- [Essence of Linear Algebra](https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab) by 3blue1brown
- [Coordinate Chart](https://twitter.com/FreyaHolmer/status/1325556229410861056) by FreyaHolmer

- [Visualizing the 4d numbers Quaternions](Ihttps://www.youtube.com/watch?v=d4EgbgTm0Bg) by 3blue1brown
- [Quaternions and 3d Rotation, Explained Interactively](https://www.youtube.com/watch?v=zjMuIxRvygQ) by 3blue1brown
- [Visualizing Quaternions](https://eater.net/quaternions) by Ben Eater and 3blue1brown
- [PyPI/quaternion](https://github.com/moble/quaternion) package by Moble


