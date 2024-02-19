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
    # Perspective
    Project from a Plane A at the position to a Plane B at a distance of one
    - The plane is always perpendicular to the camera's direction
    - Plane A is multiplied by isometric, Plane B by Zoom

    # VirtualReality
    Two halves of the screen, one for each eye, with a separation between them

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

@define
class SombreroCamera(SombreroModule):
    name: str = "Camera"

    # ------------------------------------------|
    # Camera states

    mode:       SombreroCameraMode       = SombreroCameraMode.Camera2D.field()
    projection: SombreroCameraProjection = SombreroCameraProjection.Perspective.field()
    separation: SombreroDynamics = None
    rotation:   SombreroDynamics = None
    position:   SombreroDynamics = None
    up:         SombreroDynamics = None
    zoom:       SombreroDynamics = None
    isometric:  SombreroDynamics = None
    orbital:    SombreroDynamics = None
    dolly:      SombreroDynamics = None

    # ------------------------------------------|
    # Initialization

    def __setup__(self):
        self.position = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Position",
            frequency=7, zeta=1, response=1,
            value=copy.deepcopy(GlobalBasis.Origin),
        ))
        self.separation = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}VRSeparation",
            frequency=0.5, zeta=1, response=0, value=0.05,
        ))
        self.rotation = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Rotation",
            frequency=5, zeta=1, response=0,
            value=Quaternion(1, 0, 0, 0),
        ))
        self.up = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}UP",
            frequency=1, zeta=1, response=0,
            value=copy.deepcopy(GlobalBasis.Y),
        ))
        self.zoom = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}FOV",
            frequency=3, zeta=1, response=0, value=1,
        ))
        self.isometric = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Isometric",
            frequency=1, zeta=1, response=0, value=0,
        ))
        self.orbital = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Orbital",
            frequency=1, zeta=1, response=0, value=0,
        ))
        self.dolly = self.connect(SombreroDynamics(
            prefix=self.prefix, name=f"{self.name}Dolly",
            frequency=1, zeta=1, response=0, value=0
        ))

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        # Yield decoupled dynamics
        yield from self.separation._pipeline()
        yield from self.rotation._pipeline()
        yield from self.position._pipeline()
        yield from self.up._pipeline()
        yield from self.zoom._pipeline()
        yield from self.orbital._pipeline()
        yield from self.isometric._pipeline()
        yield from self.dolly._pipeline()
        yield ShaderVariable(qualifier="uniform", type="int",  name=f"{self.prefix}CameraMode",       value=self.mode.value)
        yield ShaderVariable(qualifier="uniform", type="int",  name=f"{self.prefix}CameraProjection", value=self.projection.value)
        yield ShaderVariable(qualifier="uniform", type="vec3", name=f"{self.prefix}CameraX",          value=self.BaseX)
        yield ShaderVariable(qualifier="uniform", type="vec3", name=f"{self.prefix}CameraY",          value=self.BaseY)
        yield ShaderVariable(qualifier="uniform", type="vec3", name=f"{self.prefix}CameraZ",          value=self.BaseZ)

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
        return self.__rotate_vector__(GlobalBasis.X, self.rotation.value)
    @property
    def TargetBaseX(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.X, self.rotation.target)

    @property
    def BaseY(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Y, self.rotation.value)
    @property
    def TargetBaseY(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Y, self.rotation.target)

    @property
    def BaseZ(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Z, self.rotation.value)
    @property
    def TargetBaseZ(self) -> Vector3D:
        return self.__rotate_vector__(GlobalBasis.Z, self.rotation.target)

    # ---------------------------------------------------------------------------------------------|
    # Linear Algebra and Quaternions math

    def __angle_between_vectors__(self,
        A: Vector3D,
        B: Vector3D
    ) -> Union[float, "degrees"]:
        """
        Returns the angle between two vectors by the linear algebra formula:
        • Theta(A, B) = arccos( (A·B) / (|A|*|B|) )
        • Safe for zero vector norm divisions
        • Clips the arccos domain to [-1, 1] to avoid NaNs
        """
        A, B = DynamicNumber.extract(A, B)

        # Avoid zero divisions
        if not (LB := numpy.linalg.norm(B)):
            return 0
        if not (LA := numpy.linalg.norm(A)):
            return 0

        # Inner cosine; avoid NaNs
        cos = numpy.clip(numpy.dot(A, B)/(LA*LB), -1, 1)
        return numpy.degrees(numpy.arccos(cos))

    def __unit_vector__(self, vector: Vector3D) -> Vector3D:
        """Returns the unit vector of a given vector, safely"""
        if (factor := numpy.linalg.norm(vector)):
            return vector/factor
        return vector

    def __align_vectors__(self,
        A: Vector3D,
        B: Vector3D,
        angle: float=0
    ) -> Tuple[Vector3D, Union[float, "degrees"]]:
        A, B = DynamicNumber.extract(A, B)
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

    def __safe_vector__(self,
        *vector: Union[numpy.ndarray | tuple[float] | tuple[int] | float | int],
        dimensions: int=3,
        dtype: type=__dtype__
    ) -> numpy.ndarray:
        """
        Returns a safe numpy array from a given vector, with the correct dimensions and dtype
        """
        return numpy.array(vector, dtype=dtype).reshape(dimensions)

    def move(self, *direction: Vector3D) -> None:
        """
        Move the camera in a direction relative to the camera's position

        Args:
            direction (Vector3D): Direction to move. No movement by default
        """
        self.position.target += self.__safe_vector__(direction)

    def move_to(self, *position: Vector3D) -> None:
        """
        Moves the camera to an absolute position

        Args:
            position (Vector3D): Position to move to. Origin by default
        """
        self.position.target = self.__safe_vector__(position)

    def rotate(self,
        direction: Vector3D=GlobalBasis.Null,
        angle: Union[float, "degrees"]=0.0
    ) -> None:
        """
        Adds a cumulative rotation to the camera. Quaternion is automatic, input axis and angle

        Args:
            direction (Vector3D): Axis to rotate around. No rotation by default
            angle (degrees): Angle to rotate. No rotation by default
        """
        self.rotation.target = self.__rotation_quaternion__(direction, angle) * self.rotation.target

    def look_at(self,
        *target: Vector3D
    ) -> None:
        """
        Aligns the camera to look at a target, does not fix the "UP" direction

        Args:
            target (Vector3D): Target to look at. Origin by default
        """
        self.rotate(*self.__align_vectors__(
            self.TargetBaseZ,
            self.__safe_vector__(target) - self.position.target,
        ))

    # ---------------------------------------------------------------------------------------------|
    # Interaction

    def __update__(self):

        # # Movement

        # Start with a null move, add partial key presses
        move = copy.copy(GlobalBasis.Null)

        # WASD Shift Spacebar movement
        if self.mode == SombreroCameraMode.Camera2D:
            move += GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.W)
            move -= GlobalBasis.X * self.keyboard(SombreroKeyboard.Keys.A)
            move -= GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.S)
            move += GlobalBasis.X * self.keyboard(SombreroKeyboard.Keys.D)
        else:
            move += GlobalBasis.Z * self.keyboard(SombreroKeyboard.Keys.W)
            move -= GlobalBasis.X * self.keyboard(SombreroKeyboard.Keys.A)
            move -= GlobalBasis.Z * self.keyboard(SombreroKeyboard.Keys.S)
            move += GlobalBasis.X * self.keyboard(SombreroKeyboard.Keys.D)
            move += GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.SPACE)
            move -= GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.SHIFT)

        if move.any():
            # Make movement relative to the camera's plane
            move = self.__rotate_vector__(move, self.rotation.target)
            self.move(2 * self.__unit_vector__(move) * self.zoom * abs(self.scene.dt))

        # # Rotation around the center of the screen

        rotate = copy.copy(GlobalBasis.Null)

        # Rotation on Q and E
        if self.keyboard(SombreroKeyboard.Keys.Q):
            rotate += self.BaseZ
        if self.keyboard(SombreroKeyboard.Keys.E):
            rotate -= self.BaseZ
        if rotate.any():
            self.rotate(rotate, 45*self.scene.dt)

        # # Alignment with the "UP" direction

        if self.mode == SombreroCameraMode.Spherical:
            self.rotate(*self.__align_vectors__(self.TargetBaseX, self.up, 90))

        # # Isometric, FOV sliders
        self.isometric.target += (self.keyboard(SombreroKeyboard.Keys.T) - self.keyboard(SombreroKeyboard.Keys.G)) * abs(self.scene.dt)

    def __handle__(self, message: SombreroMessage):

        # Camera mouse drag and rotation
        if any([
            isinstance(message, SombreroMessage.Mouse.Position) and self.scene.exclusive,
            isinstance(message, SombreroMessage.Mouse.Drag)
        ]):
            match self.mode:
                case SombreroCameraMode.FreeCamera:
                    self.rotate(direction=self.zoom*self.BaseY, angle= message.du*100)
                    self.rotate(direction=self.zoom*self.BaseX, angle=-message.dv*100)

                case SombreroCameraMode.Camera2D:
                    move  = (message.du*GlobalBasis.X) + (message.dv*GlobalBasis.Y)
                    move  = self.__rotate_vector__(move, self.rotation.target)
                    self.move(self.zoom * move * (1 if self.scene.exclusive else -1))

                case SombreroCameraMode.Spherical:
                    up = 1 if (self.__angle_between_vectors__(self.TargetBaseY, self.up) < 90) else -1
                    self.rotate(direction=self.zoom*self.up*up, angle= message.du*100)
                    self.rotate(direction=self.zoom*self.BaseX, angle=-message.dv*100)

        # Change the Zoom on scroll
        if isinstance(message, SombreroMessage.Mouse.Scroll):
            self.zoom.target -= (0.05 * message.dy * self.zoom.target)

        # Change camera modes, projections and up
        if isinstance(message, SombreroMessage.Keyboard.Press):
            if message.action != 1:
                return

            # -----------------------------------------------|
            # Switch camera modes

            action = (
                message.key == SombreroKeyboard.Keys.NUMBER_1,
                message.key == SombreroKeyboard.Keys.NUMBER_2,
                message.key == SombreroKeyboard.Keys.NUMBER_3,
            )

            # Number 1: Free camera
            if action[0]:
                self.mode = SombreroCameraMode.FreeCamera

            # Number 2: 2D camera
            elif action[1]:

                # Align with the YZ plane
                self.rotate(*self.__align_vectors__(self.TargetBaseX, GlobalBasis.X))
                self.rotate(*self.__align_vectors__(self.TargetBaseY, GlobalBasis.Y))
                self.mode = SombreroCameraMode.Camera2D
                self.position.target[2] = 0
                self.isometric.target = 0
                self.zoom.target = 1

            # Number 3: Spherical camera
            elif action[2]:
                self.mode = SombreroCameraMode.Spherical

            if any(action):
                log.info(f"{self.who} • Set mode to {self.mode}")

            # -----------------------------------------------|
            # Switch what is "UP" - The magic of quaternions

            action = (
                message.key == SombreroKeyboard.Keys.I,
                message.key == SombreroKeyboard.Keys.J,
                message.key == SombreroKeyboard.Keys.K,
            )

            if action[0]:
                self.up.target = GlobalBasis.X
            elif action[1]:
                self.up.target = GlobalBasis.Y
            elif action[2]:
                self.up.target = GlobalBasis.Z

            if any(action):
                log.info(f"{self.who} • Set up to {self.up.target}")
                self.rotate(*self.__align_vectors__(self.TargetBaseZ, self.up.target))
                self.rotate(*self.__align_vectors__(self.TargetBaseY, self.up.target, 90))
                self.rotate(*self.__align_vectors__(self.TargetBaseX, self.up.target, 90))

            # -----------------------------------------------|
            # Switch projection modes

            if (message.key == SombreroKeyboard.Keys.P):
                self.projection = next(self.projection)
                log.info(f"{self.who} • Set projection to {self.projection}")

