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
    Origin = numpy.array((0, 0, 0), dtype=__dtype__)
    Null   = numpy.array((0, 0, 0), dtype=__dtype__)
    X      = numpy.array((1, 0, 0), dtype=__dtype__)
    Y      = numpy.array((0, 1, 0), dtype=__dtype__)
    Z      = numpy.array((0, 0, 1), dtype=__dtype__)

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
    - FreeCamera: Apply quaternion rotation and don't care of roll changing the "UP" direction
    - Camera2D:   Fixed direction, drag moves position on the plane of the screen, becomes isometric
    - Spherical:  Always correct such that the camera orthonormal base is pointing "UP"
    """
    FreeCamera = 1
    Camera2D   = 2
    Spherical  = 3

# -------------------------------------------------------------------------------------------------|

class Algebra:

    def rotate_vector(vector: Vector3D, R: Quaternion) -> Vector3D:
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
        # Potential speed gains, need to verify
        # if sum(quaternion.as_float_array(R)[1:]) < 1e-6:
            # return vector
        return quaternion.as_vector_part(R * quaternion.quaternion(0, *vector) * R.conjugate())

    def quaternion(axis: Vector3D, angle: Degrees) -> Quaternion:
        """Builds a quaternion that represents an rotation around an axis for an angle"""
        theta = math.radians(angle/2)
        return Quaternion(math.cos(theta), *(math.sin(theta)*axis))

    def angle(A: Vector3D, B: Vector3D) -> Degrees:
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

    def unit_vector(vector: Vector3D) -> Vector3D:
        """Returns the unit vector of a given vector, safely"""
        if (factor := numpy.linalg.norm(vector)):
            return vector/factor
        return vector

    @staticmethod
    def safe(
        *vector: Union[numpy.ndarray | tuple[float] | tuple[int] | float | int],
        dimensions: int=3,
        dtype: numpy.dtype=__dtype__
    ) -> numpy.ndarray:
        """
        Returns a safe numpy array from a given vector, with the correct dimensions and dtype
        """
        return numpy.array(vector, dtype=dtype).reshape(dimensions)

# -------------------------------------------------------------------------------------------------|

@define
class SombreroCamera(SombreroModule):
    name: str = "Camera"

    mode:       SombreroCameraMode       = SombreroCameraMode.Camera2D.Field()
    projection: SombreroCameraProjection = SombreroCameraProjection.Perspective.Field()
    separation: SombreroDynamics = None
    rotation:   SombreroDynamics = None
    position:   SombreroDynamics = None
    up:         SombreroDynamics = None
    zoom:       SombreroDynamics = None
    isometric:  SombreroDynamics = None
    orbital:    SombreroDynamics = None
    dolly:      SombreroDynamics = None

    def __build__(self):
        self.position = self.add(SombreroDynamics(
            name=f"i{self.name}Position", real=True,
            frequency=7, zeta=1, response=1,
            value=copy.deepcopy(GlobalBasis.Origin),
        ))
        self.separation = self.add(SombreroDynamics(
            name=f"i{self.name}VRSeparation", real=True,
            frequency=0.5, zeta=1, response=0, value=0.05,
        ))
        self.rotation = self.add(SombreroDynamics(
            name=f"i{self.name}Rotation", real=True,
            frequency=5, zeta=1, response=0,
            value=Quaternion(1, 0, 0, 0),
        ))
        self.up = self.add(SombreroDynamics(
            name=f"i{self.name}UP", real=True,
            frequency=1, zeta=1, response=0,
            value=copy.deepcopy(GlobalBasis.Y),
        ))
        self.zoom = self.add(SombreroDynamics(
            name=f"i{self.name}Zoom", real=True,
            frequency=3, zeta=1, response=0, value=1,
        ))
        self.isometric = self.add(SombreroDynamics(
            name=f"i{self.name}Isometric", real=True,
            frequency=1, zeta=1, response=0, value=0,
        ))
        self.orbital = self.add(SombreroDynamics(
            name=f"i{self.name}Orbital", real=True,
            frequency=1, zeta=1, response=0, value=0,
        ))
        self.dolly = self.add(SombreroDynamics(
            name=f"i{self.name}Dolly", real=True,
            frequency=1, zeta=1, response=0, value=0
        ))

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int",  f"i{self.name}Mode",       value=self.mode.value)
        yield ShaderVariable("uniform", "int",  f"i{self.name}Projection", value=self.projection.value)
        yield ShaderVariable("uniform", "vec3", f"i{self.name}X",          value=self.base_x)
        yield ShaderVariable("uniform", "vec3", f"i{self.name}Y",          value=self.base_y)
        yield ShaderVariable("uniform", "vec3", f"i{self.name}Z",          value=self.base_z)

    def includes(self) -> Iterable[str]:
        yield SHADERFLOW.RESOURCES.SHADERS_INCLUDE/"SombreroCamera.glsl"

    # ---------------------------------------------------------------------------------------------|
    # Linear Algebra and Quaternions math

    # ---------------------------------------------------------------------------------------------|
    # Actions with vectors

    def move(self, *direction: Vector3D, absolute: bool=False) -> Self:
        """
        Move the camera in a direction relative to the camera's position

        Args:
            direction: Direction to move

        Returns:
            Self: Fluent interface
        """
        if not absolute:
            self.position.target += Algebra.safe(direction)
        else:
            self.position.target  = Algebra.safe(direction)

    def rotate(self, direction: Vector3D=GlobalBasis.Null, angle: Degrees=0.0) -> Self:
        """
        Adds a cumulative rotation to the camera

        Args:
            direction: Perpendicular axis to rotate around, following the right-hand rule
            angle:     Angle to rotate

        Returns:
            Self: Fluent interface
        """
        self.rotation.target = Algebra.quaternion(direction, angle) * self.rotation.target
        self.rotation.target /= numpy.linalg.norm(quaternion.as_float_array(self.rotation.target))

    def align(self, A: Vector3D, B: Vector3D, angle: Degrees=0) -> Self:
        """
        Rotate the camera as if we were to align these two vectors
        """
        A, B = DynamicNumber.extract(A, B)
        return self.rotate(
            Algebra.unit_vector(numpy.cross(A, B)),
            Algebra.angle(A, B) - angle
        )

    def look(self, *target: Vector3D) -> Self:
        """
        Rotate the camera to look at some target point

        Args:
            target: Target point to look at

        Returns:
            Self: Fluent interface
        """
        return self.align(self.base_z_target, Algebra.safe(target) - self.position.target)

    # ---------------------------------------------------------------------------------------------|
    # Bases and directions

    @property
    def base_x(self) -> Vector3D:
        return Algebra.rotate_vector(GlobalBasis.X, self.rotation.value)
    @property
    def base_x_target(self) -> Vector3D:
        return Algebra.rotate_vector(GlobalBasis.X, self.rotation.target)

    @property
    def base_y(self) -> Vector3D:
        return Algebra.rotate_vector(GlobalBasis.Y, self.rotation.value)
    @property
    def base_y_target(self) -> Vector3D:
        return Algebra.rotate_vector(GlobalBasis.Y, self.rotation.target)

    @property
    def base_z(self) -> Vector3D:
        return Algebra.rotate_vector(GlobalBasis.Z, self.rotation.value)
    @property
    def base_z_target(self) -> Vector3D:
        return Algebra.rotate_vector(GlobalBasis.Z, self.rotation.target)

    @property
    def x(self) -> float:
        return self.position.value[0]
    @x.setter
    def x(self, value: float) -> None:
        self.position.target[0] = value

    @property
    def y(self) -> float:
        return self.position.value[1]
    @y.setter
    def y(self, value: float) -> None:
        self.position.target[1] = value

    @property
    def z(self) -> float:
        return self.position.value[2]
    @z.setter
    def z(self, value: float) -> None:
        self.position.target[2] = value

    # ---------------------------------------------------------------------------------------------|
    # Interaction

    def __update__(self):
        dt = abs(self.scene.dt or self.scene.rdt)

        # Movement on keys
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
            move -= GlobalBasis.Y * self.keyboard(SombreroKeyboard.Keys.LEFT_SHIFT)

        if move.any():
            move = Algebra.rotate_vector(move, self.rotation.target)
            self.move(2 * Algebra.unit_vector(move) * dt / self.zoom.value)

        # Rotation on Q and E
        if (rotate := sum((
            GlobalBasis.Z * self.keyboard(SombreroKeyboard.Keys.Q),
            GlobalBasis.Z * self.keyboard(SombreroKeyboard.Keys.E)*-1
        ))).any():
            rotate = Algebra.rotate_vector(rotate, self.rotation.target)
            self.rotate(rotate, 45*dt)

        # Alignment with the "UP" direction
        if self.mode == SombreroCameraMode.Spherical:
            self.align(self.base_x_target, self.up, 90)

        # Isometric on T and G
        self.dolly.target += (self.keyboard(SombreroKeyboard.Keys.T) - self.keyboard(SombreroKeyboard.Keys.G)) * dt

    def apply_zoom(self, value: float) -> None:
        self.zoom.target += value*self.zoom.target

    def __handle__(self, message: SombreroMessage):

        # Movement on Drag
        if any([
            isinstance(message, SombreroMessage.Mouse.Position) and self.scene.exclusive,
            isinstance(message, SombreroMessage.Mouse.Drag)
        ]):
            match self.mode:
                # Rotate around the camera basis itself
                case SombreroCameraMode.FreeCamera:
                    self.rotate(direction=self.base_y/self.zoom.value, angle= message.du*100)
                    self.rotate(direction=self.base_x/self.zoom.value, angle=-message.dv*100)

                # Rotate relative to the XY plane
                case SombreroCameraMode.Camera2D:
                    move = (message.du*GlobalBasis.X) + (message.dv*GlobalBasis.Y)
                    move = Algebra.rotate_vector(move, self.rotation.target)
                    self.move(move*(1 if self.scene.exclusive else -1)/self.zoom.value)

                case SombreroCameraMode.Spherical:
                    up = 1 if (Algebra.angle(self.base_y_target, self.up) < 90) else -1
                    self.rotate(direction=self.up*up /self.zoom.value, angle= message.du*100)
                    self.rotate(direction=self.base_x/self.zoom.value, angle=-message.dv*100)

        # Wheel Scroll Zoom
        if isinstance(message, SombreroMessage.Mouse.Scroll):
            self.apply_zoom(0.05*message.dy)

        # Camera alignments and modes
        if isinstance(message, SombreroMessage.Keyboard.Press) and (message.action == 1):

            # Switch camera modes
            for _ in range(1):
                if (message.key == SombreroKeyboard.Keys.NUMBER_1):
                    self.mode = SombreroCameraMode.FreeCamera
                elif (message.key == SombreroKeyboard.Keys.NUMBER_2):
                    self.align(self.base_x_target, GlobalBasis.X)
                    self.align(self.base_y_target, GlobalBasis.Y)
                    self.mode = SombreroCameraMode.Camera2D
                    self.position.target[2] = 0
                    self.isometric.target = 0
                    self.zoom.target = 1
                elif (message.key == SombreroKeyboard.Keys.NUMBER_3):
                    self.mode = SombreroCameraMode.Spherical
                else: break
            else:
                log.info(f"{self.who} • Set mode to {self.mode}")

            # What is "UP", baby don't hurt me
            for _ in range(1):
                if (message.key == SombreroKeyboard.Keys.I):
                    self.up.target = GlobalBasis.X
                elif (message.key == SombreroKeyboard.Keys.J):
                    self.up.target = GlobalBasis.Y
                elif (message.key == SombreroKeyboard.Keys.K):
                    self.up.target = GlobalBasis.Z
                else: break
            else:
                log.info(f"{self.who} • Set up to {self.up.target}")
                self.align(self.base_z_target, self.up.target)
                self.align(self.base_y_target, self.up.target, 90)
                self.align(self.base_x_target, self.up.target, 90)

            # Switch Projection
            if (message.key == SombreroKeyboard.Keys.P):
                self.projection = next(self.projection)
                log.info(f"{self.who} • Set projection to {self.projection}")
