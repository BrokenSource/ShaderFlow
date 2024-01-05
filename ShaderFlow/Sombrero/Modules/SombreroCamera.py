"""
The SombreroCamera requires some prior knowledge of a fun piece of math called Quaternions.

They are a 4D "imaginary" number that inherently represents rotations in 3D space without the
need of 3D rotation matrices (which are ugly!)*, and are pretty intuitive to use.

* https://github.com/moble/quaternion/wiki/Euler-angles-are-horrible


Great resources for understanding Quaternions:

• "Quaternions and 3d rotation, explained interactively" by 3blue1brown
  - https://www.youtube.com/watch?v=d4EgbgTm0Bg

• "Visualizing quaternions (4d numbers) with stereographic projection" by 3blue1brown
  - https://www.youtube.com/watch?v=zjMuIxRvygQ

• "Visualizing quaternion, an explorable video series" by Ben Eater and 3blue1brown
  - https://eater.net/quaternions


Useful resources on Linear Algebra and Coordinate Systems:

• "The Essence of Linear Algebra" by 3blue1brown
  - https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab

• "here, have a coordinate system chart~" by @FreyaHolmer
  - https://twitter.com/FreyaHolmer/status/1325556229410861056

  - Note: By default, SombreroCamera uses the Bottom Right Canonical Orthonormal Basis, where
          Z is "UP" and the cross product of +X and +Y is +Z (standard on math and engineering).
          The camera allows to change what is "UP" and the basis will be corrected accordingly
"""

from . import *

# -------------------------------------------------------------------------------------------------|

Quaternion = quaternion.quaternion
Vector3D   = numpy.ndarray
__dtype__  = numpy.float32

class GlobalBasis:
    Origin = numpy.array([0, 0, 0], dtype=__dtype__)
    Null   = numpy.array([0, 0, 0], dtype=__dtype__)
    X      = numpy.array([1, 0, 0], dtype=__dtype__)
    Y      = numpy.array([0, 1, 0], dtype=__dtype__)
    Z      = numpy.array([0, 0, 1], dtype=__dtype__)

# -------------------------------------------------------------------------------------------------|

class SombreroCameraProjection(BrokenEnum):
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
    Perspective     = 0
    VirtualReality  = 1
    Equirectangular = 2

class SombreroCameraMode(BrokenEnum):
    """
    How to deal with Rotations and actions on 3D or 2D space
    - Camera2D:   Fixed direction, drag moves position on the plane of the screen, becomes isometric
    - FreeCamera: Apply quaternion rotation and don't care of roll changing the "UP" direction
    - Spherical:  Always correct such that the camera orthonormal base is pointing "UP"
    """
    Camera2D   = 0
    Spherical  = 1
    FreeCamera = 2

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroCamera(SombreroModule):

    # Name of the variables on the shader relative to this camera
    name: str = "Camera"

    # ------------------------------------------|
    # Camera Mode

    __mode__: SombreroCameraMode = attrs.field(default=SombreroCameraMode.Camera2D)

    @property
    def mode(self) -> SombreroCameraMode:
        return self.__mode__

    @mode.setter
    def mode(self, value: SombreroCameraMode) -> None:
        self.__mode__ = SombreroCameraMode.smart(value)

    # ------------------------------------------|
    # Camera Projection

    __projection__: SombreroCameraProjection = attrs.field(default=SombreroCameraProjection.Perspective)

    @property
    def projection(self) -> SombreroCameraProjection:
        return self.__projection__

    @projection.setter
    def projection(self, value: SombreroCameraProjection) -> None:
        self.__projection__ = SombreroCameraProjection.smart(value)

    # ------------------------------------------|
    # VR Separation

    __vr_separation__: SombreroDynamics = None

    def __init_vr_separation__(self):
        self.__vr_separation__ = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}VRSeparation",
            frequency=0.5, zeta=1, response=0,
            type=ShaderVariableType.Float.value,
            value=0.3,
            target=0.3,
        ))

    @property
    def vr_separation(self) -> float:
        return self.__vr_separation__.value

    @vr_separation.setter
    def vr_separation(self, value: float) -> None:
        self.__vr_separation__.target = value

    # ------------------------------------------|
    # Rotation

    __rotation__: SombreroDynamics = None

    def __init_rotation__(self):
        self.__rotation__ = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Rotation",
            frequency=4, zeta=0.707, response=0,
            type=ShaderVariableType.Vec4.value,
            value=copy.deepcopy(Quaternion(1, 0, 0, 0)),
            target=copy.deepcopy(Quaternion(1, 0, 0, 0)),
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
        self.__position__ = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Position",
            frequency=5, zeta=0.707, response=1,
            type=ShaderVariableType.Vec3.value,
            value=copy.deepcopy(GlobalBasis.Origin),
            target=copy.deepcopy(GlobalBasis.Origin),
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
        self.__up__ = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}UP",
            frequency=1, zeta=1, response=0,
            type=ShaderVariableType.Vec3.value,
            value=copy.deepcopy(GlobalBasis.Z),
            target=copy.deepcopy(GlobalBasis.Z),
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
        self.__fov__ = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}FOV",
            frequency=3, zeta=1, response=0,
            type=ShaderVariableType.Float.value,
            value=1,
            target=1,
        ))

    @property
    def fov(self) -> Union[float, "units"]:
        return self.__fov__.value

    @fov.setter
    def fov(self, value: Union[float, "units"]) -> None:
        self.__fov__.target = value

    # ------------------------------------------|
    # Isometric

    __isometric__: SombreroDynamics = None

    def __init_isometric__(self):
        self.__isometric__ = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Isometric",
            frequency=1, zeta=1, response=0,
            type=ShaderVariableType.Float.value,
            value=0,
            target=0,
        ))

    @property
    def isometric(self) -> float:
        return self.__isometric__.value

    @isometric.setter
    def isometric(self, value: float) -> None:
        self.__isometric__.target = numpy.clip(value, 0, 1)

    # ------------------------------------------|
    # Initialization

    def setup(self):
        self.__init_vr_separation__()
        self.__init_rotation__()
        self.__init_position__()
        self.__init_up__()
        self.__init_fov__()
        self.__init_isometric__()

    def pipeline(self) -> Iterable[ShaderVariable]:
        # Yield decoupled dynamics
        yield from self.__vr_separation__.pipeline()
        yield from self.__rotation__.pipeline()
        yield from self.__position__.pipeline()
        yield from self.__up__.pipeline()
        yield from self.__fov__.pipeline()
        yield from self.__isometric__.pipeline()

        # Camera modes
        yield ShaderVariable(qualifier="uniform", type="int", name=f"{self.prefix}CameraMode",       value=self.mode.value)
        yield ShaderVariable(qualifier="uniform", type="int", name=f"{self.prefix}CameraProjection", value=self.projection.value)

        # Camera basis
        yield ShaderVariable(qualifier="uniform", type="vec3", name=f"{self.prefix}CameraX", value=self.BaseX)
        yield ShaderVariable(qualifier="uniform", type="vec3", name=f"{self.prefix}CameraY", value=self.BaseY)
        yield ShaderVariable(qualifier="uniform", type="vec3", name=f"{self.prefix}CameraZ", value=self.BaseZ)


    def includes(self) -> Dict[str, str]:
        return dict(SombreroCamera=(SHADERFLOW.RESOURCES.SHADERS_INCLUDE/"SombreroCamera.glsl").read_text())

    # ---------------------------------------------------------------------------------------------|
    # Bases and directions

    def __rotate_vector__(self, vector: Vector3D, R: Quaternion) -> Vector3D:
        """
        Applies a Quaternion rotation to a vector.

        • Permalink: https://github.com/moble/quaternion/blob/2286c479016097b156682eddaf927036c192c22e/src/quaternion/__init__.py#L654

        As numpy-quaternion documentation says, we should avoid quaternion.rotate_vectors
        when we don't have multiple vectors to rotate, and we mean a lot of vectors.

        Args:
            vector (Vector3D): Vector to rotate
            R (Quaternion): Rotation quaternion

        Returns:
            Vector3D: Rotated vector
        """
        return quaternion.as_vector_part(R * quaternion.from_vector_part(vector) * R.conjugate())

    @property
    def BaseX(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.X, self.__rotation__.value)
    @property
    def TargetBaseX(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.X, self.__rotation__.target)

    @property
    def BaseY(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Y, self.__rotation__.value)
    @property
    def TargetBaseY(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Y, self.__rotation__.target)

    @property
    def BaseZ(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Z, self.__rotation__.value)
    @property
    def TargetBaseZ(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Z, self.__rotation__.target)

    # ---------------------------------------------------------------------------------------------|
    # Linear Algebra and Quaternions math

    def __angle_between_vectors__(self, A: Vector3D, B: Vector3D) -> Union[float, "degrees"]:
        """
        Returns the angle between two vectors by the linear algebra formula:
        • Theta(A, B) = arccos( (A·B) / (|A|*|B|) )
        """
        return math.degrees(math.acos(numpy.dot(A, B) / (numpy.linalg.norm(A) * numpy.linalg.norm(B))))

    def __unit_vector__(self, vector: Vector3D) -> Vector3D:
        """Returns the unit vector of a given vector"""
        if (factor := numpy.linalg.norm(vector)) == 0:
            return vector
        return vector / factor

    def __align_vectors__(self, A: Vector3D, B: Vector3D, angle: float=0) -> Tuple[Vector3D, Union[float, "degrees"]]:
        return (
            self.__unit_vector__(numpy.cross(A, B)),
            self.__angle_between_vectors__(A, B) - angle
        )

    def __rotation_quaternion__(self,
        axis: Vector3D,
        angle: Union[float, "degrees"]
    ) -> Quaternion:
        """Builds a quaternion that represents an rotation around an axis for an angle"""
        theta = math.radians(angle/2)
        return Quaternion(math.cos(theta), *(math.sin(theta)*axis))

    # ---------------------------------------------------------------------------------------------|
    # Actions with vectors

    def move(self,
        direction: Vector3D=GlobalBasis.Null
    ) -> None:
        """Move the camera in some direction, do multiply it by speed, sensitivity, etc"""
        self.__position__.target += direction

    def rotate(self,
        direction: Vector3D=GlobalBasis.Null,
        angle: Union[float, "degrees"]=0.0
    ) -> None:
        """Adds a cumulative rotation to the camera. Quaternion is automatic, input axis and angle"""
        self.__rotation__.target = self.__rotation_quaternion__(direction, angle) * self.__rotation__.target

    # ---------------------------------------------------------------------------------------------|
    # Interaction

    def update(self):

        # # Movement

        # Start with a null move, add partial key presses
        move = copy.copy(GlobalBasis.Null)

        # WASD Shift Spacebar movement
        if self.mode == SombreroCameraMode.Camera2D:
            move += GlobalBasis.Z * self.keyboard(SombreroKeyboard.Keys.W)
            move += GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.A)
            move -= GlobalBasis.Z * self.keyboard(SombreroKeyboard.Keys.S)
            move -= GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.D)

            # Fix the movement to the camera's plane
            if move.any():
                move = self.__rotate_vector__(move, self.__rotation__.target)
        else:
            if self.keyboard(SombreroKeyboard.Keys.W):     move += self.BaseX
            if self.keyboard(SombreroKeyboard.Keys.A):     move += self.BaseY
            if self.keyboard(SombreroKeyboard.Keys.S):     move -= self.BaseX
            if self.keyboard(SombreroKeyboard.Keys.D):     move -= self.BaseY
            if self.keyboard(SombreroKeyboard.Keys.SPACE): move += self.BaseZ
            if self.keyboard(SombreroKeyboard.Keys.SHIFT): move -= self.BaseZ

        if move.any():
            self.move(2 * self.__unit_vector__(move) * self.fov * abs(self.scene.dt))

        # # Rotation around the center of the screen

        rotate = copy.copy(GlobalBasis.Null)

        # Rotation on Q and E
        if self.keyboard(SombreroKeyboard.Keys.Q):
            rotate -= self.BaseX
        if self.keyboard(SombreroKeyboard.Keys.E):
            rotate += self.BaseX
        if rotate.any():
            self.rotate(rotate, 45*self.scene.dt)

        # # Alignment with the "UP" direction

        if self.mode == SombreroCameraMode.Spherical:
            self.rotate(*self.__align_vectors__(self.TargetBaseY, self.up, 90))

        # # Isometric, FOV sliders
        self.isometric += 5 * (self.keyboard(SombreroKeyboard.Keys.T) - self.keyboard(SombreroKeyboard.Keys.G)) * abs(self.scene.dt)

    def handle(self, message: SombreroMessage):

        # Camera mouse drag and rotation
        if any([
            isinstance(message, SombreroMessage.Mouse.Position) and self.scene.exclusive,
            isinstance(message, SombreroMessage.Mouse.Drag)
        ]):
            if self.mode == SombreroCameraMode.Camera2D:
                move  = message.du * GlobalBasis.Y
                move -= message.dv * GlobalBasis.Z
                move  = self.__rotate_vector__(move, self.__rotation__.target)
                self.move(self.fov * move * (-1 if self.scene.exclusive else 1))
            else:
                self.rotate(direction=self.fov*self.BaseZ, angle=-message.du*100)
                self.rotate(direction=self.fov*self.BaseY, angle=-message.dv*100)

        # Change the Field of View on scroll
        if isinstance(message, SombreroMessage.Mouse.Scroll):
            self.fov -= self.fov*(0.2*message.dy)

        # Change camera modes, projections and up
        if isinstance(message, SombreroMessage.Keyboard.Press):
            if message.action != 1:
                return

            # -----------------------------------------------|
            # Switch camera modes

            __action__ = (
                message.key == SombreroKeyboard.Keys.NUMBER_1,
                message.key == SombreroKeyboard.Keys.NUMBER_2,
                message.key == SombreroKeyboard.Keys.NUMBER_3,
            )

            # Number 1: Free camera
            if  __action__[0]:
                self.mode = SombreroCameraMode.FreeCamera

            # Number 2: 2D camera
            elif __action__[1]:

                # Align with the YZ plane
                self.rotate(*self.__align_vectors__(self.TargetBaseZ, GlobalBasis.Z))
                self.rotate(*self.__align_vectors__(self.TargetBaseY, GlobalBasis.Y))
                self.mode = SombreroCameraMode.Camera2D
                self.__position__.target[0] = 0
                self.isometric = 0
                self.fov = 1

            # Number 3: Spherical camera
            elif __action__[2]:
                self.mode = SombreroCameraMode.Spherical

            if any(__action__):
                log.info(f"{self.who} • Set mode to {self.mode}")

            # -----------------------------------------------|
            # Switch what is "UP" - The magic of quaternions

            __action__ = (
                message.key == SombreroKeyboard.Keys.I,
                message.key == SombreroKeyboard.Keys.J,
                message.key == SombreroKeyboard.Keys.K,
            )

            if   __action__[0]:
                self.up = GlobalBasis.X
            elif __action__[1]:
                self.up = GlobalBasis.Y
            elif __action__[2]:
                self.up = GlobalBasis.Z

            if any(__action__):
                log.info(f"{self.who} • Set up to {self.__up__.target}")
                self.rotate(*self.__align_vectors__(self.TargetBaseZ, self.__up__.target))
                self.rotate(*self.__align_vectors__(self.TargetBaseY, self.__up__.target, 90))
                self.rotate(*self.__align_vectors__(self.TargetBaseX, self.__up__.target, 90))

            # -----------------------------------------------|
            # Switch projection modes

            if message.key == SombreroKeyboard.Keys.P:
                self.projection = SombreroCameraProjection.next(self.projection)
                log.info(f"{self.who} • Set projection to {self.projection}")

