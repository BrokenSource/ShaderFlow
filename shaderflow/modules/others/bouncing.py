import random
from collections.abc import Iterable
from math import cos, sin

import numpy as np
from attr import define

from broken import clamp
from broken.core.extra.loaders import LoadableImage, LoadImage
from broken.types import TAU, Degrees
from shaderflow.module import ShaderModule
from shaderflow.texture import ShaderTexture
from shaderflow.variable import ShaderVariable, Uniform


@define
class ShaderBouncing(ShaderModule):
    name: str = "iBounce"
    position: np.ndarray = None
    velocity: np.ndarray = None
    aspect_ratio: float = 1

    def setup(self):
        self.set_velocity_polar(1, random.uniform(0, TAU))
        self.position = np.array((0.0, 0.0))

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
        self.velocity = magnitude*np.array((cos(angle), sin(angle)))

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
        ratios = np.zeros((steps, 1), dtype=np.float32)
        image = np.array(LoadImage(image))
        width, height, _ = image.shape
        bigger = max(width, height)

        import cv2

        # image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = image[:, :, 3]

        # Make anew image with a centered raw copy
        square = np.zeros((bigger, bigger), dtype=np.uint8)
        x, y = (bigger-width)//2, (bigger-height)//2
        square[x:x+width, y:y+height] = image

        # Rotate the image and find its alpha content bounding box
        for i, angle in enumerate(np.linspace(0, 360, steps)):
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
