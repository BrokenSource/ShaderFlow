from __future__ import annotations

from . import *

# This SombreroCamera requires some prior knowledge of a fun piece of math called Quaternions.
#
# They are a 4D "imaginary" number that inherently represents rotations in 3D space without the
# need of 3D rotation matrices
#
# Great resources for understanding Quaternions:
#
# • "Quaternions and 3d rotation, explained interactively" by 3blue1brown
#   - https://www.youtube.com/watch?v=d4EgbgTm0Bg
#
# • "Visualizing quaternions (4d numbers) with stereographic projection" by 3blue1brown
#   - https://www.youtube.com/watch?v=zjMuIxRvygQ
#
# • "Visualizing quaternion, an explorable video series"
#   - https://eater.net/quaternions
#

# -------------------------------------------------------------------------------------------------|

Quaternion = quaternion.quaternion
__dtype__ = numpy.float32

class Direction:
    Null = numpy.array([0, 0, 0], dtype=__dtype__)
    X    = numpy.array([1, 0, 0], dtype=__dtype__)
    Y    = numpy.array([0, 1, 0], dtype=__dtype__)
    Z    = numpy.array([0, 0, 1], dtype=__dtype__)

Origin = numpy.array([0, 0, 0], dtype=__dtype__)

CanonicalBase = DotMap(
    X=Direction.X,
    Y=Direction.Y,
    Z=Direction.Z,
)

# -------------------------------------------------------------------------------------------------|

class CameraProjectionMode(BrokenEnum):
    """
    # Plane
    Project from the position to a plane at a distance defined by the FOV, zoom and isometric
    - The plane is always perpendicular to the camera's direction
    - The plane size is multiplied by zoom, at a distance defined by the FOV
    - Isometric defines the "project from" plane centered at the camera's position

    # Equirectangular
    The "360°" videos we see on platforms like YouTube, it's a simples sphere projected to the
    screen where X defines the azimuth and Y the inclination, ranging such that they sweep the sphere
    """
    Plane           = "Plane"
    Equirectangular = "Equirectangular"

class CameraMode(BrokenEnum):
    """
    How to deal with Rotations and actions on 3D or 2D space
    - TwoD:      Fixed direction, drag moves position on the plane of the screen, becomes isometric
    - FreeCamera: Apply quaternion rotation and don't care of roll changing the "UP" direction
    - LockUp:     Always correct such that the camera orthonormal base is pointing "UP"
    """
    TwoD       = "2D"
    FreeCamera = "3D Free Camera"
    Aligned    = "3D Aligned UP"

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroCamera(SombreroModule):

    # ---------------------------------------------------------------------------------------------|
    # Modes

    mode      : CameraMode           = CameraMode.FreeCamera
    projection: CameraProjectionMode = CameraProjectionMode.Plane

    # ---------------------------------------------------------------------------------------------|
    # Position related

    # Rotation

    __rotation__: BrokenSecondOrderDynamics = attrs.Factory(
        lambda: BrokenSecondOrderDynamics(value=Quaternion(1, 0, 0, 0), frequency=7, zeta=0.707, response=0))

    @property
    def rotation(self) -> Quaternion:
        """Rotation is a quaternion that represents the camera's cumulative rotation applied to the canonical base"""
        return self.__rotation__.value

    @rotation.setter
    def rotation(self, value) -> None:
        self.__rotation__.target = value

    # ------------------------------------------|

    # Position

    __position__: BrokenSecondOrderDynamics = attrs.Factory(lambda: BrokenSecondOrderDynamics(
        value=Origin, frequency=1, zeta=1, response=0))

    @property
    def position(self) -> numpy.ndarray:
        """Position is a plain Vector3 point in space"""
        return self.__position__.value

    @position.setter
    def position(self, value) -> None:
        self.__position__.target = value

    # ------------------------------------------|

    # Up direction

    __up__: BrokenSecondOrderDynamics = attrs.Factory(
        lambda: BrokenSecondOrderDynamics(value=Direction.Z, frequency=1, zeta=1, response=0))

    @property
    def up(self) -> Direction:
        """
        For CameraMode.LockUp:
        - Defines the direction the camera should always point "UP"

        For other modes:
        - Does nothing as the axis "UP" is non-locked
        """
        return self.__up__.value

    @up.setter
    def up(self, value: Direction) -> None:
        self.__up__.target = value

    # ---------------------------------------------------------------------------------------------|
    # Projection related

    __fov__: BrokenSecondOrderDynamics = attrs.Factory(
        lambda: BrokenSecondOrderDynamics(value=100, frequency=3, zeta=1, response=0))

    @property
    def fov(self) -> type[float, "degrees"]:
        return self.__fov__.value

    @fov.setter
    def fov(self, value: type[float, "degrees"]) -> None:
        self.__fov__.target = value

    @property
    def fov_distance(self) -> float:
        """
        For CameraProjectionMode.Plane:
        - It is the angle formed between the position and the middle of the edge of the projected plane
        - $tan(theta/2) = 1/distance$, so $distance = 1/tan(theta/2)$
        - Angles bigger than 180° gives zero divisions, bigger values inverts the view

        For CameraProjectionMode.Equirectangular:
        - It is the maximum azimuth and inclination to project relative to the camera's direction
        - Azimuth goes from -180° to 180° and inclination from -90 to 90° so range is (0, 180) for FOV
        """
        return 1/math.tan(math.radians(self.__fov__.value)/2)

    # ------------------------------------------|

    __isometric__: BrokenSecondOrderDynamics = attrs.Factory(
        lambda: BrokenSecondOrderDynamics(value=0, frequency=1, zeta=1, response=0))

    @property
    def isometric(self) -> float:
        """
        Defines the side length of the origin plane of projections to the field of view plane
        - If the origin projection is a point (isometric=0) then the camera is on 100% perspective
        - Values of (isometric=1) gives parallel rays, so the camera is on 100% isometric projection
        """
        return self.__isometric__.value

    @isometric.setter
    def isometric(self, value: float) -> None:
        self.__isometric__.target = value

    # ---------------------------------------------------------------------------------------------|
    # Sombrero Module implementation

    def align_vectors(self, A: numpy.ndarray, B: numpy.ndarray) -> tuple[numpy.ndarray, float]:
        return (
            self.__unit_vector__(numpy.cross(A, B)),
            math.degrees(self.__angle_between_vectors__(A, B))
        )

    def align_spherical(self, A: numpy.ndarray, B: numpy.ndarray) -> tuple[numpy.ndarray, float]:
        return (
            self.__unit_vector__(numpy.cross(A, B)),
            math.degrees(self.__angle_between_vectors__(A, B)) - 90
        )

    def update(self, time: float, dt: float) -> None:
        """Update the camera's dynamics"""
        self.__rotation__.update(dt=dt)
        self.__position__.update(dt=dt)
        self.__fov__.update(dt=dt)
        self.__isometric__.update(dt=dt)

        # Normalize the rotation quaternion
        self.__rotation__.value /= abs(self.__rotation__.value)

        # Align BaseZ to Upwards on Locked mode
        if self.mode == CameraMode.FreeCamera:
            pass
        if self.mode == CameraMode.Aligned:
            self.rotate(*self.align_spherical(quaternion.rotate_vectors(self.__rotation__.target, Direction.Y), self.up))
        if self.mode == CameraMode.TwoD:
            self.rotate(*self.align_vectors(quaternion.rotate_vectors(self.__rotation__.target, Direction.Z), Direction.Z))
            self.rotate(*self.align_vectors(
                quaternion.rotate_vectors(self.__rotation__.target, Direction.Y),
                Direction.Y
            ))

        # # Keyboard
        if self.mode == CameraMode.TwoD:
            ...
        else:
            # WASD Space Shift Movement
            move = copy.copy(Direction.Null)
            if self.sombrero.keyboard.pressed(glfw.KEY_W):
                move += self.Forward
            if self.sombrero.keyboard.pressed(glfw.KEY_A):
                move += self.Leftward
            if self.sombrero.keyboard.pressed(glfw.KEY_S):
                move += self.Backward
            if self.sombrero.keyboard.pressed(glfw.KEY_D):
                move += self.Rightward
            if self.sombrero.keyboard.pressed(glfw.KEY_SPACE):
                move += self.Upward
            if self.sombrero.keyboard.pressed(glfw.KEY_LEFT_SHIFT):
                move += self.Downward
            move = 0.01 * self.__unit_vector__(move)
            self.move(move)

        # Pipe values
        self.sombrero.pipe(
            iCameraPosition  = self.position,
            iCameraX         = self.BaseX,
            iCameraY         = self.BaseY,
            iCameraZ         = self.BaseZ,
            iCameraFOV       = self.fov,
            iCameraFOVD      = self.fov_distance,
            iCameraIsometric = self.isometric,
        )

    def bind(self) -> None:

        # # Bind Window actions
        self.sombrero.window_mouse_drag_event_func.bind(self.mouse_drag_event_func)
        self.sombrero.window_mouse_scroll_event_func.bind(self.mouse_scroll_event_func)
        self.sombrero.window_key_event_func.bind(self.key_event_func)

    # ---------------------------------------------------------------------------------------------|
    # Bases and directions

    @property
    def BaseX(self) -> numpy.ndarray:
        return quaternion.rotate_vectors(self.__rotation__.value, Direction.X)
    @property
    def BaseY(self) -> numpy.ndarray:
        return quaternion.rotate_vectors(self.__rotation__.value, Direction.Y)
    @property
    def BaseZ(self) -> numpy.ndarray:
        return quaternion.rotate_vectors(self.__rotation__.value, Direction.Z)

    @property
    def base(self) -> DotMap:
        """
        Gets the canonical based rotated by the camera's current rotation
        - X should always points to the direction the camera is facing
        - Z should point to the natural "UP" direction
        - Y should point "to the left" of the camera
        """
        return DotMap(X=self.BaseX, Y=self.BaseY, Z=self.BaseZ)

    @property
    def Forward(self)   -> numpy.ndarray: return  self.BaseX
    @property
    def Backward(self)  -> numpy.ndarray: return -self.BaseX
    @property
    def Leftward(self)  -> numpy.ndarray: return  self.BaseY
    @property
    def Rightward(self) -> numpy.ndarray: return -self.BaseY
    @property
    def Upward(self)    -> numpy.ndarray: return  self.BaseZ
    @property
    def Downward(self)  -> numpy.ndarray: return -self.BaseZ

    # ---------------------------------------------------------------------------------------------|
    # Linear Algebra and Quaternions math

    def __angle_between_vectors__(self, a: numpy.ndarray, b: numpy.ndarray) -> float:
        """Returns the angle between two vectors"""
        return math.acos(numpy.dot(a, b) / (numpy.linalg.norm(a) * numpy.linalg.norm(b)))

    def __unit_vector__(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Returns the unit vector of a given vector"""
        if (factor := numpy.linalg.norm(vector)) != 0:
            return vector / factor
        return vector

    def __rotation_quaternion__(self,
        direction: numpy.ndarray,
        angle: type[float, "degrees"]
    ) -> Quaternion:
        """Builds a quaternion that represents an rotation around an axis for an angle"""
        sin, cos = math.sin(math.radians(angle/2)), math.cos(math.radians(angle/2))
        return Quaternion(cos, *(sin*direction))

    def move(self,
        direction: Option[numpy.ndarray, Direction, SombreroCamera.base]=Direction.Null
    ) -> None:
        """Move the camera in some direction, do multiply it by speed, sensitivity, etc"""
        self.__position__.target += direction

    def rotate(self,
        direction: Option[numpy.ndarray, Direction, SombreroCamera.base, Direction]=Direction.Null,
        angle: type[float, "degrees"]=0.0
    ) -> None:
        """Adds a cumulative rotation to the camera. Quaternion is automatic, input axis and angle"""
        self.__rotation__.target = self.__rotation_quaternion__(direction, angle) * self.__rotation__.target

    # ---------------------------------------------------------------------------------------------|
    # Window events and their actions

    def mouse_drag_event_func(self, x: int, y: int, dx: int, dy: int) -> None:
        if self.mode == CameraMode.TwoD:
            self.move(0.01 * (dx*self.base.Y + dy*self.base.Z) * (self.fov_distance/2))
        else:
            self.rotate(direction=self.base.Z, angle=-0.3*dx)
            self.rotate(direction=self.base.Y, angle= 0.3*dy)

    def mouse_scroll_event_func(self, x: int, y: int) -> None:
        if self.sombrero.keyboard.pressed(glfw.KEY_LEFT_ALT):
            self.__isometric__.target += 0.1 * y
        else:
            self.fov = self.fov * (1 - y/3)

    def key_event_func(self, key: int, action: int, modifiers: int) -> None:
        # Tab switches between modes
        if key == glfw.KEY_TAB and action == glfw.PRESS:
            if self.mode == CameraMode.TwoD:
                self.mode = CameraMode.FreeCamera
                self.position[0] = 0
                self.isometric = 0

            elif self.mode == CameraMode.FreeCamera:
                self.mode = CameraMode.Aligned

            elif self.mode == CameraMode.Aligned:
                self.mode = CameraMode.TwoD
                self.isometric = 0
                self.up = Direction.Z
            log.info(f"Switch to camera mode ({self.mode.value})")

    # ---------------------------------------------------------------------------------------------|
    # Easy directions relative to the camera base

    # Debug

    def info(self):
        print("Position: ", self.position)
        print("Base:     ", self.base)
        print()

# C = SombreroCamera()
# C.rotate(Direction.Y, 90)
# C.up = Direction.Y

# # start = time.time()
# for _ in range(9000):
#     # C.rotate(C.Rightward, 15)
#     # C.rotate(C.Upward,    15)
#     # C.rotate(C.Leftward,  15)
#     # C.rotate(C.Downward,  15)
#     C.info()
#     C.fix_up()
#     time.sleep(0.2)

# print((9000*4)/(time.time() - start))

# C.move(C.Forward)
# C.info()

# exit()

# print("Default camera")
# C.info()

# print("Rotate GlobalZ 90")
# C.rotate(Direction.Z, 90)
# C.info()

# print("Rotate BaseX 90")
# C.rotate(C.Forward, 90)
# C.info()

# print("Move forwrad one unit")
# C.move(C.Forward)
# C.info()

# print("Move Global Forward X one unit")
# C.move(CanonicalBase.X)
# C.info()

# exit()

