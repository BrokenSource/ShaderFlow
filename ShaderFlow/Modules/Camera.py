"""
The Camera requires some prior knowledge of a fun piece of math called Quaternions.

They are 4D complex numbers that perfectly represents rotations in 3D space without the
need of 3D rotation matrices (which are ugly!)*, and are pretty intuitive to use.

* https://github.com/moble/quaternion/wiki/Euler-angles-are-horrible


Great resources for understanding Quaternions:

• "Quaternions and 3d rotation, explained interactively" by @3blue1brown
  - https://www.youtube.com/watch?v=d4EgbgTm0Bg

• "Visualizing quaternions (4d numbers) with stereographic projection" by @3blue1brown
  - https://www.youtube.com/watch?v=zjMuIxRvygQ

• "Visualizing quaternion, an explorable video series" by Ben Eater and @3blue1brown
  - https://eater.net/quaternions


Useful resources on Linear Algebra and Coordinate Systems:

• "The Essence of Linear Algebra" by @3blue1brown
  - https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab

• "here, have a coordinate system chart~" by @FreyaHolmer
  - https://twitter.com/FreyaHolmer/status/1325556229410861056
"""

import math
from collections.abc import Iterable
from typing import Self, TypeAlias, Union

import numpy
from attrs import define

from Broken import BrokenEnum, block_modules, clamp
from Broken.Types import Degrees
from ShaderFlow import SHADERFLOW
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Modules.Dynamics import DynamicNumber, ShaderDynamics
from ShaderFlow.Modules.Keyboard import ShaderKeyboard
from ShaderFlow.Variable import ShaderVariable, Uniform

# Don't import fancy interpolation
with block_modules("scipy"):
    import quaternion

# ------------------------------------------------------------------------------------------------ #

Quaternion: TypeAlias = quaternion.quaternion
Vector3D:   TypeAlias = numpy.ndarray
_dtype:     TypeAlias = numpy.float64

class GlobalBasis:
    Origin   = numpy.array(( 0,  0,  0), dtype=_dtype)
    Null     = numpy.array(( 0,  0,  0), dtype=_dtype)
    Up       = numpy.array(( 0,  1,  0), dtype=_dtype)
    Down     = numpy.array(( 0, -1,  0), dtype=_dtype)
    Left     = numpy.array((-1,  0,  0), dtype=_dtype)
    Right    = numpy.array(( 1,  0,  0), dtype=_dtype)
    Forward  = numpy.array(( 0,  0,  1), dtype=_dtype)
    Backward = numpy.array(( 0,  0, -1), dtype=_dtype)

# ------------------------------------------------------------------------------------------------ #

class CameraProjection(BrokenEnum):
    Perspective = 0
    """
    Project from a Plane A at the position to a Plane B at a distance of one
    - The plane is always perpendicular to the camera's direction
    - Plane A is multiplied by isometric, Plane B by Zoom
    """

    VirtualReality = 1
    """Two halves of the screen, one for each eye, with a separation between them"""

    Equirectangular = 2
    """The 360° videos of platforms like YouTube, it's a simples sphere projected to the screen
    where X defines the azimuth and Y the inclination, ranging such that they sweep the sphere"""

class CameraMode(BrokenEnum):
    FreeCamera = 0
    """Free to rotate in any direction - do not ensure the 'up' direction matches the zenith"""

    Camera2D = 1
    """Fixed direction, drag moves position on the plane of the screen"""

    Spherical = 2
    """Always correct such that the camera orthonormal base is pointing 'UP'"""

# ------------------------------------------------------------------------------------------------ #

class Algebra:

    def quaternion(axis: Vector3D, angle: Degrees) -> Quaternion:
        """Builds a quaternion that represents an rotation around an axis for an angle"""
        return Quaternion(math.cos(theta := math.radians(angle/2)), *(math.sin(theta)*axis))

    def rotate_vector(vector: Vector3D, R: Quaternion) -> Vector3D:
        """Applies a Quaternion rotation to a vector"""
        return quaternion.as_vector_part(R * quaternion.quaternion(0, *vector) * R.conjugate())

    def angle(A: Vector3D, B: Vector3D) -> Degrees:
        """
        Returns the angle between two vectors by the linear algebra formula:
        • Theta(A, B) = arccos( (A·B) / (|A|*|B|) )
        • Safe for zero vector norm divisions
        • Clips the arccos domain to [-1, 1] to avoid NaNs
        """
        A, B = DynamicNumber.extract(A, B)

        # Avoid zero divisions
        if not (LA := numpy.linalg.norm(A)):
            return 0.0
        if not (LB := numpy.linalg.norm(B)):
            return 0.0

        # Avoid NaNs by clipping domain
        cos = numpy.clip(numpy.dot(A, B)/(LA*LB), -1, 1)
        return numpy.degrees(numpy.arccos(cos))

    def unit_vector(vector: Vector3D) -> Vector3D:
        """Returns the unit vector of a given vector, safely"""
        if (magnitude := numpy.linalg.norm(vector)):
            return (vector/magnitude)
        return vector

    @staticmethod
    def safe(
        *vector: Union[numpy.ndarray, tuple[float], float, int],
        dimensions: int=3,
        dtype: numpy.dtype=_dtype
    ) -> numpy.ndarray:
        """
        Returns a safe numpy array from a given vector, with the correct dimensions and dtype
        """
        return numpy.array(vector, dtype=dtype).reshape(dimensions)

# ------------------------------------------------------------------------------------------------ #

@define
class ShaderCamera(ShaderModule):
    name:       str = "iCamera"
    mode:       CameraMode       = CameraMode.Camera2D.field()
    projection: CameraProjection = CameraProjection.Perspective.field()
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
            value=numpy.copy(GlobalBasis.Origin)
        )
        self.separation = ShaderDynamics(scene=self.scene,
            name=f"{self.name}VRSeparation", real=True,
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
            value=numpy.copy(GlobalBasis.Up)
        )
        self.zoom = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Zoom", real=True,
            frequency=3, zeta=1, response=0, value=1
        )
        self.isometric = ShaderDynamics(scene=self.scene,
            name=f"{self.name}Isometric", real=True,
            frequency=1, zeta=1, response=0, value=0
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
    def fov(self) -> Degrees:
        """The vertical field of view angle, considers the isometric factor"""
        return 2.0 * math.degrees(math.atan(self.zoom.value - self.isometric.value))

    @fov.setter
    def fov(self, value: Degrees):
        self.zoom.target = math.tan(math.radians(value)/2.0) + self.isometric.value

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int",  f"{self.name}Mode",       value=self.mode)
        yield Uniform("int",  f"{self.name}Projection", value=self.projection)
        yield Uniform("vec3", f"{self.name}Right",      value=self.right)
        yield Uniform("vec3", f"{self.name}Upward",     value=self.up)
        yield Uniform("vec3", f"{self.name}Forward",    value=self.forward)

    def includes(self) -> Iterable[str]:
        yield SHADERFLOW.RESOURCES.SHADERS_INCLUDE/"Camera.glsl"

    # ---------------------------------------------------------------------------------------------|
    # Actions with vectors

    def move(self, *direction: Vector3D, absolute: bool=False) -> Self:
        """Move the camera in a direction relative to the camera's position"""
        self.position.target += Algebra.safe(direction) - (self.position.target * absolute)
        return self

    def rotate(self, direction: Vector3D=GlobalBasis.Null, angle: Degrees=0.0) -> Self:
        """Adds a cumulative rotation to the camera. Use "look" for absolute rotation"""
        self.rotation.target  = Algebra.quaternion(direction, angle) * self.rotation.target
        self.rotation.target /= numpy.linalg.norm(quaternion.as_float_array(self.rotation.target))
        return self

    def rotate2d(self, angle: Degrees=0.0) -> Self:
        """Aligns the UP vector rotated on FORWARD direction. Same math angle on a cartesian plane"""
        target = Algebra.rotate_vector(self.zenith.value, Algebra.quaternion(self.forward_target, angle))
        return self.align(self.up_target, target)

    def align(self, A: Vector3D, B: Vector3D, angle: Degrees=0.0) -> Self:
        """Rotate the camera as if we were to align these two vectors"""
        A, B = DynamicNumber.extract(A, B)
        return self.rotate(
            Algebra.unit_vector(numpy.cross(A, B)),
            Algebra.angle(A, B) - angle
        )

    def look(self, *target: Vector3D) -> Self:
        """Rotate the camera to look at some target point"""
        return self.align(self.forward_target, Algebra.safe(target) - self.position.target)

    # ---------------------------------------------------------------------------------------------|
    # Interaction

    def update(self):
        dt = abs(self.scene.dt or self.scene.rdt)

        # Movement on keys
        move = numpy.copy(GlobalBasis.Null)

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
        rotate = numpy.copy(GlobalBasis.Null)
        if self.scene.keyboard(ShaderKeyboard.Keys.Q): rotate += GlobalBasis.Forward
        if self.scene.keyboard(ShaderKeyboard.Keys.E): rotate += GlobalBasis.Backward
        if rotate.any(): self.rotate(Algebra.rotate_vector(rotate, self.rotation.target), 45*dt)

        # Alignment with the "UP" direction
        if self.mode == CameraMode.Spherical:
            self.align(self.right_target, self.zenith.target, 90)

        # Isometric on T and G
        if (self.scene.keyboard(ShaderKeyboard.Keys.T)):
            self.isometric.target = clamp(self.isometric.target + 0.5*dt, 0, 1)
        if (self.scene.keyboard(ShaderKeyboard.Keys.G)):
            self.isometric.target = clamp(self.isometric.target - 0.5*dt, 0, 1)

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
                self.rotate(direction=self.up*self.zoom.value, angle= message.du*100)
                self.rotate(direction=self.right*self.zoom.value, angle=-message.dv*100)

            # Rotate relative to the XY plane
            elif (self.mode == CameraMode.Camera2D):
                move = (message.du*GlobalBasis.Right) + (message.dv*GlobalBasis.Up)
                move = Algebra.rotate_vector(move, self.rotation.target)
                self.move(move*(1 if self.scene.exclusive else -1)*self.zoom.value)

            elif (self.mode == CameraMode.Spherical):
                up = 1 if (Algebra.angle(self.up_target, self.zenith) < 90) else -1
                self.rotate(direction=self.zenith*up *self.zoom.value, angle= message.du*100)
                self.rotate(direction=self.right*self.zoom.value, angle=-message.dv*100)

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
                self.log_info(f"• Set mode to {self.mode}")

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
                self.log_info(f"• Set zenith to {self.zenith.target}")
                self.align(self.forward_target, self.zenith.target)
                self.align(self.up_target, self.zenith.target, 90)
                self.align(self.right_target, self.zenith.target, 90)

            # Switch Projection
            if (message.key == ShaderKeyboard.Keys.P):
                self.projection = next(self.projection)
                self.log_info(f"• Set projection to {self.projection}")

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
