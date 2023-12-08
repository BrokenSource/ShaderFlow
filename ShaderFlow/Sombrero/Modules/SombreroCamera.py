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
Vector3D   = numpy.ndarray
__dtype__  = numpy.float32

class Direction:
    Null = numpy.array([0, 0, 0], dtype=__dtype__)
    X    = numpy.array([1, 0, 0], dtype=__dtype__)
    Y    = numpy.array([0, 1, 0], dtype=__dtype__)
    Z    = numpy.array([0, 0, 1], dtype=__dtype__)

Origin = numpy.array([0, 0, 0], dtype=__dtype__)

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
    Camera2D   = 0
    FreeCamera = 1
    Aligned    = 2

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroCamera(SombreroModule):

    # Name of the variables on the shader relative to this camera
    name: str = "Camera"

    # ------------------------------------------|
    # Camera Mode

    __mode__: CameraMode = attrs.field(default=CameraMode.Camera2D)

    @property
    def mode(self) -> CameraMode:
        return self.__mode__

    @mode.setter
    def mode(self, value: CameraMode) -> None:
        # Fixme: Add to pipeline
        self.__mode__ = CameraMode.smart(value)

    # ------------------------------------------|
    # Camera Projection

    __projection__: CameraProjectionMode = attrs.field(default=CameraProjectionMode.Plane)

    @property
    def projection(self) -> CameraProjectionMode:
        return self.__projection__

    @projection.setter
    def projection(self, value: CameraProjectionMode) -> None:
        self.__projection__ = CameraProjectionMode.smart(value)

    # ------------------------------------------|
    # Rotation

    __rotation__: SombreroDynamics = None

    def __init_rotation__(self):
        self.__rotation__ = self.add(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Rotation",
            frequency=7, zeta=0.707, response=0,
            type=None,
            value=copy.deepcopy(Quaternion(1, 0, 0, 0)),
        ))

    @property
    def rotation(self) -> Quaternion:
        return self.__rotation__.value

    @rotation.setter
    def rotation(self, value: Quaternion) -> None:
        self.__rotation__.target = value

    # ------------------------------------------|
    # Position

    __position__: SombreroDynamics = None

    def __init_position__(self):
        self.__position__ = self.add(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Position",
            frequency=5, zeta=0.707, response=1,
            type=ShaderVariableType.Vec3.value,
            value=copy.deepcopy(Origin),
        ))

    @property
    def position(self) -> Vector3D:
        return self.__position__.value

    @position.setter
    def position(self, value: Vector3D) -> None:
        self.__position__.target = value

    # ------------------------------------------|
    # Up direction

    __up__: SombreroDynamics = None

    def __init_up__(self):
        self.__up__ = self.add(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Up",
            frequency=1, zeta=1, response=0,
            type=ShaderVariableType.Vec3.value,
            value=copy.deepcopy(Direction.Z),
        ))

    @property
    def up(self) -> Vector3D:
        return self.__up__.value

    @up.setter
    def up(self, value: Vector3D) -> None:
        self.__up__.target = value

    # ------------------------------------------|
    # Field of View

    __fov__: SombreroDynamics = None

    def __init_fov__(self):
        self.__fov__ = self.add(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}FOV",
            frequency=3, zeta=1, response=0,
            type=ShaderVariableType.Float.value,
            value=100,
            target=100,
        ))

    @property
    def fov(self) -> Union[float, "degrees"]:
        return self.__fov__.value

    @fov.setter
    def fov(self, value: Union[float, "degrees"]) -> None:
        self.__fov__.target = value

    @property
    def fov_distance(self) -> float:
        # Fixme: FOV Maths and add to pipeline
        return 1/math.tan(math.radians(self.__fov__.value)/2)

    # ------------------------------------------|
    # Isometric

    __isometric__: SombreroDynamics = None

    def __init_isometric__(self):
        self.__isometric__ = self.add(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Isometric",
            frequency=1, zeta=1, response=0,
            type=ShaderVariableType.Vec3.value,
            value=0,
            target=0,
        ))

    @property
    def isometric(self) -> float:
        return self.__isometric__.value

    @isometric.setter
    def isometric(self, value: float) -> None:
        self.__isometric__.target = value

    # ------------------------------------------|
    # Initialization

    def setup(self):
        self.__init_rotation__()
        self.__init_position__()
        self.__init_up__()
        self.__init_fov__()
        self.__init_isometric__()

    # ---------------------------------------------------------------------------------------------|
    # Bases and directions

    @property
    def BaseX(self) -> Vector3D:
        return quaternion.rotate_vectors(self.__rotation__.value, Direction.X)

    @property
    def BaseY(self) -> Vector3D:
        return quaternion.rotate_vectors(self.__rotation__.value, Direction.Y)

    @property
    def BaseZ(self) -> Vector3D:
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
    def Forward(self)   -> Vector3D: return  self.BaseX
    @property
    def Backward(self)  -> Vector3D: return -self.BaseX
    @property
    def Leftward(self)  -> Vector3D: return  self.BaseY
    @property
    def Rightward(self) -> Vector3D: return -self.BaseY
    @property
    def Upward(self)    -> Vector3D: return  self.BaseZ
    @property
    def Downward(self)  -> Vector3D: return -self.BaseZ

    # ---------------------------------------------------------------------------------------------|
    # Linear Algebra and Quaternions math

    def __angle_between_vectors__(self, a: Vector3D, b: Vector3D) -> float:
        """Returns the angle between two vectors"""
        return math.acos(numpy.dot(a, b) / (numpy.linalg.norm(a) * numpy.linalg.norm(b)))

    def __unit_vector__(self, vector: Vector3D) -> Vector3D:
        """Returns the unit vector of a given vector"""
        if (factor := numpy.linalg.norm(vector)) != 0:
            return vector / factor
        return vector

    def __rotation_quaternion__(self, direction: Vector3D, angle: Union[float, "degrees"]) -> Quaternion:
        """Builds a quaternion that represents an rotation around an axis for an angle"""
        sin, cos = math.sin(math.radians(angle/2)), math.cos(math.radians(angle/2))
        return Quaternion(cos, *(sin*direction))

    def move(self, direction: Vector3D=Direction.Null) -> None:
        """Move the camera in some direction, do multiply it by speed, sensitivity, etc"""
        self.__position__.target += direction

    def rotate(self, direction: Vector3D, angle: Union[float, "degrees"]=0.0) -> None:
        """Adds a cumulative rotation to the camera. Quaternion is automatic, input axis and angle"""
        self.__rotation__.target += self.__rotation_quaternion__(direction, angle) * self.__rotation__.target

    # ---------------------------------------------------------------------------------------------|
    # Interaction

    def handle(self, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Mouse.Drag):
            if self.mode == CameraMode.Camera2D:
                self.move(-message.du*self.BaseX - message.dv*self.BaseY)
            else:
                self.rotate(direction=self.BaseZ, angle=-message.du)
                self.rotate(direction=self.BaseY, angle= message.dv)

        if isinstance(message, SombreroMessage.Mouse.Scroll):
            pass

        if isinstance(message, SombreroMessage.Keyboard.Unicode):
            pass
