"""
Quaternions resources:
- https://www.youtube.com/watch?v=d4EgbgTm0Bg (3blue1brown)
- https://www.youtube.com/watch?v=zjMuIxRvygQ (3blue1brown)
- https://eater.net/quaternions (3blue1brown, Ben Eater)
- https://github.com/moble/quaternion

Linear Algebra resources:
- https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab (3blue1brown)
- https://twitter.com/FreyaHolmer/status/1325556229410861056 (FreyaHolmer)

ShaderFlow's camera follows a Y-up, left-handed coordinate system, as mappings
between the screen projection planes and ray marching are one-to-one in xy

Note: https://github.com/moble/quaternion/wiki/Euler-angles-are-horrible
"""

import math
import sys
from collections.abc import Iterable
from enum import Enum
from typing import Self, TypeAlias
from unittest.mock import patch

import numpy as np
from attrs import define, field

import shaderflow
from shaderflow import logger
from shaderflow.dynamics import DynamicNumber, ShaderDynamics
from shaderflow.keyboard import ShaderKeyboard
from shaderflow.message import ShaderMessage
from shaderflow.module import ShaderModule
from shaderflow.variable import ShaderVariable, Uniform

# Save import time on blocking advanced calculus
with patch.dict(sys.modules, scipy=None, numba=None):
    import quaternion

# ---------------------------------------------------------------------------- #

Quaternion: TypeAlias = quaternion.quaternion
Vector3D:   TypeAlias = np.ndarray
_dtype:     TypeAlias = np.float64

class GlobalBasis:
    Origin   = np.array(( 0,  0,  0), dtype=_dtype)
    Null     = np.array(( 0,  0,  0), dtype=_dtype)
    Up       = np.array(( 0,  1,  0), dtype=_dtype)
    Down     = np.array(( 0, -1,  0), dtype=_dtype)
    Left     = np.array((-1,  0,  0), dtype=_dtype)
    Right    = np.array(( 1,  0,  0), dtype=_dtype)
    Forward  = np.array(( 0,  0,  1), dtype=_dtype)
    Backward = np.array(( 0,  0, -1), dtype=_dtype)

# ---------------------------------------------------------------------------- #

class CameraProjection(Enum):

    Perspective: int = 0
    """
    Project from a Plane A at the position to a Plane B at a distance of one
    - The plane is always perpendicular to the camera's direction
    - Plane A is multiplied by isometric, Plane B by Zoom
    """

    Stereoscopic: int = 1
    """Two halves of the screen, one for each eye, with a separation between them"""

    Equirectangular: int = 2
    """The 360° videos of platforms like YouTube, it's a simples sphere projected to the screen
    where X defines the azimuth and Y the inclination, ranging such that they sweep the sphere"""

    def __next__(self) -> Self:
        return (self.value + 1) % len(tuple(type(self)))

    @classmethod
    def _missing_(cls, value: object):
        if value in ("perspective", "default"):
            return cls.Perspective
        elif value in ("stereoscopic", "stereo", "vr", "sbs"):
            return cls.Stereoscopic
        elif value in ("spherical", "equirectangular", "360"):
            return cls.Equirectangular
        raise ValueError(f"{value} is not a valid {cls.__name__}")


class CameraMode(Enum):

    FreeCamera: int = 0
    """Free to rotate in any direction - do not ensure the 'up' direction matches the zenith"""

    Camera2D: int = 1
    """Fixed direction, drag moves position on the plane of the screen"""

    Spherical: int = 2
    """Always correct such that the camera orthonormal base is pointing 'UP'"""

    @classmethod
    def _missing_(cls, value: object):
        if value in ("free", "freecamera"):
            return cls.FreeCamera
        elif value in ("2d", "plane", "flat"):
            return cls.Camera2D
        elif value in ("spherical", "aligned"):
            return cls.Spherical
        raise ValueError(f"{value} is not a valid {cls.__name__}")

# ---------------------------------------------------------------------------- #

class Algebra:

    def quaternion(axis: Vector3D, degrees: float) -> Quaternion:
        """Builds a quaternion that represents an rotation around an axis for an angle"""
        return Quaternion(math.cos(theta := math.radians(degrees/2)), *(math.sin(theta)*axis))

    def rotate_vector(vector: Vector3D, R: Quaternion) -> Vector3D:
        """Applies a Quaternion rotation to a vector"""
        return quaternion.as_vector_part(R * quaternion.quaternion(0, *vector) * R.conjugate())

    def angle(A: Vector3D, B: Vector3D) -> float:
        """
        Returns the angle between two vectors by the linear algebra formula:
        • Theta(A, B) = arccos( (A·B) / (|A|*|B|) )
        • Safe for zero vector norm divisions
        • Clips the arccos domain to [-1, 1] to avoid NaNs
        """
        A, B = DynamicNumber.extract(A, B)

        # Avoid zero divisions
        if not (LA := np.linalg.norm(A)):
            return 0.0
        if not (LB := np.linalg.norm(B)):
            return 0.0

        # Avoid NaNs by clipping domain
        cos = np.clip(np.dot(A, B)/(LA*LB), -1, 1)
        return np.degrees(np.arccos(cos))

    def unit_vector(vector: Vector3D) -> Vector3D:
        """Returns the unit vector of a given vector, safely"""
        if (magnitude := np.linalg.norm(vector)):
            return (vector/magnitude)
        return vector

# ---------------------------------------------------------------------------- #

@define
class ShaderCamera(ShaderModule):
    name:       str = "iCamera"
    mode:       CameraMode       = field(default=CameraMode.Camera2D, converter=CameraMode)
    projection: CameraProjection = field(default=CameraProjection.Perspective, converter=CameraProjection)
    separation: ShaderDynamics = None
    rotation:   ShaderDynamics = None
    position:   ShaderDynamics = None
    zenith:     ShaderDynamics = None
    zoom:       ShaderDynamics = None
    isometric:  ShaderDynamics = None
    orbital:    ShaderDynamics = None
    dolly:      ShaderDynamics = None

    def build(self):
        self.position = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Position", real=True,
            frequency=4, zeta=1, response=0,
            value=np.copy(GlobalBasis.Origin)
        )
        self.separation = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Separation", real=True,
            frequency=0.5, zeta=1, response=0, value=0.05
        )
        self.rotation = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Rotation", real=True, primary=False,
            frequency=5, zeta=1, response=0,
            value=Quaternion(1, 0, 0, 0)
        )
        self.zenith = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Zenith", real=True,
            frequency=1, zeta=1, response=0,
            value=np.copy(GlobalBasis.Up)
        )
        self.zoom = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Zoom", real=True,
            frequency=3, zeta=1, response=0, value=1
        )
        self.isometric = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Isometric", real=True,
            frequency=1, zeta=1, response=0, value=0
        )
        self.focal_length = ShaderDynamics(scene=self.scene,
            name=f"{self.name}FocalLength", real=True,
            frequency=1, zeta=1, response=0, value=1
        )
        self.orbital = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Orbital", real=True,
            frequency=1, zeta=1, response=0, value=0
        )
        self.dolly = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Dolly", real=True,
            frequency=1, zeta=1, response=0, value=0
        )

    @property
    def fov(self) -> float:
        """The vertical field of view angle, considers the isometric factor"""
        return 2.0 * math.degrees(math.atan(self.zoom.value - self.isometric.value))

    @fov.setter
    def fov(self, value: float):
        self.zoom.target = math.tan(math.radians(value)/2.0) + self.isometric.value

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int",  f"{self.name}Mode",       value=self.mode)
        yield Uniform("int",  f"{self.name}Projection", value=self.projection)
        yield Uniform("vec3", f"{self.name}Right",      value=self.right)
        yield Uniform("vec3", f"{self.name}Upward",     value=self.up)
        yield Uniform("vec3", f"{self.name}Forward",    value=self.forward)

    def includes(self) -> Iterable[str]:
        yield (shaderflow.resources/"shaders"/"include"/"camera.glsl")

    # ---------------------------------------------------------------------------------------------|
    # Actions with vectors

    def move(self, direction: Vector3D, absolute: bool=False) -> Self:
        """Move the camera in a direction relative to the camera's position"""
        self.position.target += direction - (self.position.target * absolute)
        return self

    def rotate(self, direction: Vector3D=GlobalBasis.Null, degrees: float=0.0) -> Self:
        """Adds a cumulative rotation to the camera. Use "look" for absolute rotation"""
        self.rotation.target  = Algebra.quaternion(direction, degrees) * self.rotation.target
        self.rotation.target /= np.linalg.norm(quaternion.as_float_array(self.rotation.target))
        return self

    def rotate2d(self, degrees: float=0.0) -> Self:
        """Aligns the UP vector rotated on FORWARD direction. Same math angle on a cartesian plane"""
        target = Algebra.rotate_vector(self.zenith.value, Algebra.quaternion(self.forward_target, degrees))
        return self.align(self.up_target, target)

    def align(self, A: Vector3D, B: Vector3D, degrees: float=0.0) -> Self:
        """Rotate the camera as if we were to align these two vectors"""
        A, B = DynamicNumber.extract(A, B)
        return self.rotate(
            Algebra.unit_vector(np.cross(A, B)),
            Algebra.angle(A, B) - degrees
        )

    def look(self, target: Vector3D) -> Self:
        """Rotate the camera to look at some target point"""
        return self.align(self.forward_target, target - self.position.target)

    # ---------------------------------------------------------------------------------------------|
    # Interaction

    def update(self):
        dt = abs(self.scene.dt or self.scene.rdt)

        # Movement on keys
        move = np.copy(GlobalBasis.Null)

        # WASD Shift Spacebar movement
        if self.mode == CameraMode.Camera2D:
            if self.scene.keyboard(ShaderKeyboard.Keys.W): move += GlobalBasis.Up
            if self.scene.keyboard(ShaderKeyboard.Keys.A): move += GlobalBasis.Left
            if self.scene.keyboard(ShaderKeyboard.Keys.S): move += GlobalBasis.Down
            if self.scene.keyboard(ShaderKeyboard.Keys.D): move += GlobalBasis.Right
        else:
            if self.scene.keyboard(ShaderKeyboard.Keys.W): move += GlobalBasis.Forward
            if self.scene.keyboard(ShaderKeyboard.Keys.A): move += GlobalBasis.Left
            if self.scene.keyboard(ShaderKeyboard.Keys.S): move += GlobalBasis.Backward
            if self.scene.keyboard(ShaderKeyboard.Keys.D): move += GlobalBasis.Right
            if self.scene.keyboard(ShaderKeyboard.Keys.SPACE): move += GlobalBasis.Up
            if self.scene.keyboard(ShaderKeyboard.Keys.LEFT_SHIFT): move += GlobalBasis.Down

        if move.any():
            move = Algebra.rotate_vector(move, self.rotation.target)
            self.move(2 * Algebra.unit_vector(move) * self.zoom.value * dt)

        # Rotation on Q and E
        rotate = np.copy(GlobalBasis.Null)
        if self.scene.keyboard(ShaderKeyboard.Keys.Q): rotate += GlobalBasis.Forward
        if self.scene.keyboard(ShaderKeyboard.Keys.E): rotate += GlobalBasis.Backward
        if rotate.any(): self.rotate(Algebra.rotate_vector(rotate, self.rotation.target), 45*dt)

        # Alignment with the "UP" direction
        if self.mode == CameraMode.Spherical:
            self.align(self.right_target, self.zenith.target, 90)

        # Isometric on T and G
        if (self.scene.keyboard(ShaderKeyboard.Keys.T)):
            self.isometric.target = min(max(0, self.isometric.target + 0.5*dt), 1)
        if (self.scene.keyboard(ShaderKeyboard.Keys.G)):
            self.isometric.target = min(max(0, self.isometric.target - 0.5*dt), 1)

    def apply_zoom(self, value: float) -> None:
        # Note: Ensures a zoom in then out returns to the same value
        if (value > 0):
            self.zoom.target *= (1 + value)
        else:
            self.zoom.target /= (1 - value)

    def handle(self, message: ShaderMessage):

        # Movement on Drag
        if any([
            isinstance(message, ShaderMessage.Mouse.Position) and self.scene.exclusive,
            isinstance(message, ShaderMessage.Mouse.Drag)
        ]):
            if not (self.scene.mouse_buttons[1] or self.scene.exclusive):
                return

            # Rotate around the camera basis itself
            if (self.mode == CameraMode.FreeCamera):
                self.rotate(direction=self.up*self.zoom.value, degrees= message.du*100)
                self.rotate(direction=self.right*self.zoom.value, degrees=-message.dv*100)

            # Rotate relative to the XY plane
            elif (self.mode == CameraMode.Camera2D):
                move = (message.du*GlobalBasis.Right) + (message.dv*GlobalBasis.Up)
                move = Algebra.rotate_vector(move, self.rotation.target)
                self.move(move*(1 if self.scene.exclusive else -1)*self.zoom.value)

            elif (self.mode == CameraMode.Spherical):
                up = 1 if (Algebra.angle(self.up_target, self.zenith) < 90) else -1
                self.rotate(direction=self.zenith*up *self.zoom.value, degrees= message.du*100)
                self.rotate(direction=self.right*self.zoom.value, degrees=-message.dv*100)

        # Wheel Scroll Zoom
        elif isinstance(message, ShaderMessage.Mouse.Scroll):
            self.apply_zoom(-0.05*message.dy)

        # Camera alignments and modes
        elif isinstance(message, ShaderMessage.Keyboard.Press) and (message.action == 1):

            # Switch camera modes
            for _ in range(1):
                if (message.key == ShaderKeyboard.Keys.NUMBER_1):
                    self.mode = CameraMode.FreeCamera
                elif (message.key == ShaderKeyboard.Keys.NUMBER_2):
                    self.align(self.right_target,  GlobalBasis.Right)
                    self.align(self.up_target, GlobalBasis.Up)
                    self.mode = CameraMode.Camera2D
                    self.position.target[2] = 0
                    self.isometric.target = 0
                    self.zoom.target = 1
                elif (message.key == ShaderKeyboard.Keys.NUMBER_3):
                    self.mode = CameraMode.Spherical
                else: break
            else:
                logger.info(f"• Set mode to {self.mode}")

            # What is "UP", baby don't hurt me
            for _ in range(1):
                if (message.key == ShaderKeyboard.Keys.I):
                    self.zenith.target = GlobalBasis.Right
                elif (message.key == ShaderKeyboard.Keys.J):
                    self.zenith.target = GlobalBasis.Up
                elif (message.key == ShaderKeyboard.Keys.K):
                    self.zenith.target = GlobalBasis.Forward
                else: break
            else:
                logger.info(f"• Set zenith to {self.zenith.target}")
                self.align(self.forward_target, self.zenith.target)
                self.align(self.up_target, self.zenith.target, 90)
                self.align(self.right_target, self.zenith.target, 90)

            # Switch Projection
            if (message.key == ShaderKeyboard.Keys.P):
                self.projection = next(self.projection)
                logger.info(f"• Set projection to {self.projection}")

    # ---------------------------------------------------------------------------------------------|
    # Bases and directions

    @property
    def right(self) -> Vector3D:
        """The current 'right' direction relative to the camera"""
        return Algebra.rotate_vector(GlobalBasis.Right, self.rotation.value)

    @property
    def right_target(self) -> Vector3D:
        """The target 'right' direction the camera is aligning to"""
        return Algebra.rotate_vector(GlobalBasis.Right, self.rotation.target)

    @property
    def left(self) -> Vector3D:
        """The current 'left' direction relative to the camera"""
        return (-1) * self.right

    @property
    def left_target(self) -> Vector3D:
        """The target 'left' direction the camera is aligning to"""
        return (-1) * self.right_target

    @property
    def up(self) -> Vector3D:
        """The current 'upwards' direction relative to the camera"""
        return Algebra.rotate_vector(GlobalBasis.Up, self.rotation.value)

    @property
    def up_target(self) -> Vector3D:
        """The target 'upwards' direction the camera is aligning to"""
        return Algebra.rotate_vector(GlobalBasis.Up, self.rotation.target)

    @property
    def down(self) -> Vector3D:
        """The current 'downwards' direction relative to the camera"""
        return (-1) * self.up

    @property
    def down_target(self) -> Vector3D:
        """The target 'downwards' direction the camera is aligning to"""
        return (-1) * self.up_target

    @property
    def forward(self) -> Vector3D:
        """The current 'forward' direction relative to the camera"""
        return Algebra.rotate_vector(GlobalBasis.Forward, self.rotation.value)

    @property
    def forward_target(self) -> Vector3D:
        """The target 'forward' direction the camera is aligning to"""
        return Algebra.rotate_vector(GlobalBasis.Forward, self.rotation.target)

    @property
    def backward(self) -> Vector3D:
        """The current 'backward' direction relative to the camera"""
        return (-1) * self.forward

    @property
    def backward_target(self) -> Vector3D:
        """The target 'backward' direction the camera is aligning to"""
        return (-1) * self.forward_target

    # # Positions

    @property
    def x(self) -> float:
        """The current X position of the camera"""
        return self.position.value[0]

    @x.setter
    def x(self, value: float):
        self.position.target[0] = value

    @property
    def y(self) -> float:
        """The current Y position of the camera"""
        return self.position.value[1]

    @y.setter
    def y(self, value: float):
        self.position.target[1] = value

    @property
    def z(self) -> float:
        """The current Z position of the camera"""
        return self.position.value[2]

    @z.setter
    def z(self, value: float):
        self.position.target[2] = value
