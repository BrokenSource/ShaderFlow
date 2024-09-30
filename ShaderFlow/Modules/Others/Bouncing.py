import random
from math import cos, sin
from typing import Iterable

import numpy
from attr import define
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Texture import ShaderTexture
from ShaderFlow.Variable import ShaderVariable, Uniform

from Broken import clamp
from Broken.Loaders import LoadableImage, LoaderImage
from Broken.Types import TAU, Degrees


@define
class ShaderBouncing(ShaderModule):
    name: str = "iBounce"
    position: numpy.ndarray = None
    velocity: numpy.ndarray = None
    aspect_ratio: float = 1

    def setup(self):
        self.set_velocity_polar(1, random.uniform(0, TAU))
        self.position = numpy.array((0.0, 0.0))

    def update(self):
        self.position += (self.velocity * self.scene.dt)

        for i, limit in enumerate((self.aspect_ratio, 1)):
            if abs(self.position[i]) > limit:
                self.velocity[i] = -self.velocity[i]
                self.position[i] = clamp(self.position[i], -limit, limit)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("vec2", f"{self.name}Position", self.position)
        yield Uniform("vec2", f"{self.name}Velocity", self.velocity)

    # # Quality of Life

    def set_velocity_polar(self, magnitude: float, angle: Degrees):
        self.velocity = magnitude*numpy.array((cos(angle), sin(angle)))

    @property
    def x(self) -> float:
        return self.position[0]

    @property
    def y(self) -> float:
        return self.position[1]

    @x.setter
    def x(self, value: float):
        self.position[0] = value

    @y.setter
    def y(self, value: float):
        self.position[1] = value

    # # Advanced

    def advanced_ratios(self, image: LoadableImage, steps: int=1000) -> ShaderTexture:
        """Get a texture of `aspect_ratio(angle)` from linspace(0, tau, steps)"""
        ratios = numpy.zeros((steps, 1), dtype=numpy.float32)
        image = numpy.array(LoaderImage(image))
        width, height, _ = image.shape
        bigger = max(width, height)

        import cv2

        # image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = image[:, :, 3]

        # Make anew image with a centered raw copy
        square = numpy.zeros((bigger, bigger), dtype=numpy.uint8)
        x, y = (bigger-width)//2, (bigger-height)//2
        square[x:x+width, y:y+height] = image

        # Rotate the image and find its alpha content bounding box
        for i, angle in enumerate(numpy.linspace(0, 360, steps)):
            rotation = cv2.getRotationMatrix2D((bigger/2, bigger/2), angle, 1)
            rotated  = cv2.warpAffine(square, rotation, (bigger, bigger))
            thresh   = cv2.threshold(rotated, 4, 255, cv2.THRESH_BINARY)[1]
            contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
            _, _, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
            ratios[i][0] = (w/h)

        return ShaderTexture(
            name=f"{self.name}AspectRatio",
            scene=self.scene,
            components=1,
            width=steps,
            height=1,
        ).from_numpy(ratios)
