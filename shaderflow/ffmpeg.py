from __future__ import annotations

import functools
import io
import re
import subprocess
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
from typing import (
    Annotated,
    Generator,
    Literal,
    Optional,
    Self,
    TypeAlias,
    Union,
)

import numpy as np
import typer
from attrs import define
from halo import Halo
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typer import Option

from broken.path import BrokenPath
from broken.system import Host
from broken.typerx import BrokenTyper
from broken.utils import denum, every, flatten, nearest, shell
from shaderflow import logger

# ---------------------------------------------------------------------------- #

class FFmpegModuleBase(BaseModel, ABC):
    model_config = ConfigDict(
        use_attribute_docstrings=True,
        validate_assignment=True,
    )

    @abstractmethod
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        ...

# ---------------------------------------------------------------------------- #

class FFmpegInputPath(FFmpegModuleBase):
    path: Path

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        return ("-i", self.path)


class FFmpegInputPipe(FFmpegModuleBase):
    class Format(str, Enum):
        Rawvideo   = "rawvideo"
        Image2Pipe = "image2pipe"
        Null       = "null"

    format: Annotated[Optional[Format],
        Option("--format", "-f")] = \
        Field(Format.Rawvideo)

    class PixelFormat(str, Enum):
        YUV420P = "yuv420p"
        YUV444P = "yuv444p"
        RGB24   = "rgb24"
        RGBA    = "rgba"

    pixel_format: Annotated[PixelFormat,
        Option("--pixel-format", "-p")] = \
        Field(PixelFormat.RGB24)

    width: int = Field(1920, gt=0)
    height: int = Field(1080, gt=0)
    framerate: float = Field(60.0, ge=1.0)

    @field_validator("framerate", mode="plain")
    def validate_framerate(cls, value: Union[float, str]) -> float:
        return eval(str(value))

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-f", denum(self.format))
        yield ("-s", f"{self.width}x{self.height}")
        yield ("-pix_fmt", denum(self.pixel_format))
        yield ("-r", self.framerate)
        yield ("-i", "-")


FFmpegInputType: TypeAlias = Union[
    FFmpegInputPath,
    FFmpegInputPipe,
]

# ---------------------------------------------------------------------------- #

class FFmpegOutputPath(FFmpegModuleBase):

    path: Annotated[Path,
        typer.Argument(help="The output file path")] = \
        Field(...)

    class PixelFormat(str, Enum):
        YUV420P = "yuv420p"
        YUV444P = "yuv444p"

    pixel_format: Annotated[Optional[PixelFormat],
        Option("--pixel-format", "-p")] = \
        Field(PixelFormat.YUV420P)

    overwrite: Annotated[bool,
        Option("--overwrite", "-y", " /--no-overwrite", " /-n")] = \
        Field(True)

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-pix_fmt", denum(self.pixel_format))
        yield (self.path, self.overwrite*"-y")


class FFmpegOutputPipe(FFmpegModuleBase):

    class Format(str, Enum):
        Rawvideo   = "rawvideo"
        Image2Pipe = "image2pipe"
        Matroska   = "matroska"
        Mpegts     = "mpegts"
        Null       = "null"

    format: Annotated[Optional[Format],
        Option("--format", "-f")] = \
        Field("mpegts")

    class PixelFormat(str, Enum):
        RGB24 = "rgb24"
        RGBA  = "rgba"

    pixel_format: Annotated[Optional[PixelFormat],
        Option("--pixel-format", "-p")] = \
        Field(None)

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-f", denum(self.format))
        yield every("-pix_fmt", denum(self.pixel_format))
        yield "pipe:1"


FFmpegOutputType = Union[
    FFmpegOutputPipe,
    FFmpegOutputPath,
]

# ---------------------------------------------------------------------------- #

# Note: See full help with `ffmpeg -h encoder=h264`
# https://trac.ffmpeg.org/wiki/Encode/H.264
class FFmpegVideoCodecH264(FFmpegModuleBase):
    """Encode the video with libx264"""

    class Preset(str, Enum):
        UltraFast = "ultrafast"
        SuperFast = "superfast"
        VeryFast  = "veryfast"
        Faster    = "faster"
        Fast      = "fast"
        Medium    = "medium"
        Slow      = "slow"
        Slower    = "slower"
        VerySlow  = "veryslow"

    preset: Annotated[Optional[Preset],
        Option("--preset", "-p")] = \
        Field(Preset.Slow)
    """Time to spend for better compression"""

    class Tune(str, Enum):
        Film        = "film"
        Animation   = "animation"
        Grain       = "grain"
        StillImage  = "stillimage"
        FastDecode  = "fastdecode"
        ZeroLatency = "zerolatency"

    tune: Annotated[Optional[Tune],
        Option("--tune", "-t")] = \
        Field(None)
    """Optimize for certain types of media"""

    class Profile(str, Enum):
        Baseline = "baseline"
        Main     = "main"
        High     = "high"
        High10   = "high10"
        High422  = "high422"
        High444p = "high444p"

    profile: Annotated[Optional[Profile],
        Option("--profile")] = \
        Field(None)
    """Features baseline, go conservative for compatibility"""

    faststart: Annotated[bool,
        Option("--faststart", " /--no-faststart", hidden=True)] = \
        Field(True)

    rgb: Annotated[bool,
        Option("--rgb", " /--yuv")] = \
        Field(False)
    """Use RGB colorspace instead of YUV"""

    crf: Annotated[int,
        Option("--crf", "-c", min=0, max=51)] = \
        Field(20, ge=0, le=51)
    """Constant Rate Factor, 0 is lossless, 51 is the worst quality"""

    bitrate: Annotated[Optional[int],
        Option("--bitrate", "-b", min=0)] = \
        Field(None, ge=0)
    """Bitrate in kilobits/s, the higher the better quality and file size"""

    x264params: Annotated[Optional[list[str]],
        Option("--x264-params", hidden=True)] = \
        Field(None)
    """Additional options to pass to x264"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:v", "libx264rgb" if self.rgb else "libx264")
        yield every("-movflags", "+faststart"*self.faststart)
        yield every("-profile", denum(self.profile))
        yield every("-preset", denum(self.preset))
        yield every("-tune", denum(self.tune))
        yield every("-b:v", self.bitrate)
        yield every("-crf", self.crf)
        yield every("-x264opts", ":".join(self.x264params or []))


# Note: See full help with `ffmpeg -h encoder=h264_nvenc`
class FFmpegVideoCodecH264_NVENC(FFmpegModuleBase):
    """Encode the video with Nvenc h264"""

    class Preset(str, Enum):
        HighQuality2Passes        = "slow"
        HighQuality1Pass          = "medium"
        HighPerformance1Pass      = "fast"
        HighPerformance           = "hp"
        HighQuality               = "hq"
        Balanced                  = "bd"
        LowLatency                = "ll"
        LowLatencyHighQuality     = "llhq"
        LowLatencyHighPerformance = "llhp"
        Lossless                  = "lossless"
        LosslessHighPerformance   = "losslesshp"
        Fastest                   = "p1"
        Faster                    = "p2"
        Fast                      = "p3"
        Medium                    = "p4"
        Slow                      = "p5"
        Slower                    = "p6"
        Slowest                   = "p7"

    preset: Annotated[Optional[Preset],
        Option("--preset", "-p")] = \
        Field(Preset.Medium)
    """Time to spend for better compression"""

    class Tune(str, Enum):
        HighQuality     = "hq"
        LowLatency      = "ll"
        UltraLowLatency = "ull"
        Lossless        = "lossless"

    tune: Annotated[Optional[Tune],
        Option("--tune", "-t")] = \
        Field(Tune.HighQuality)
    """Tune the encoder for a specific tier of performance"""

    class Profile(str, Enum):
        Baseline = "baseline"
        Main     = "main"
        High     = "high"
        High444p = "high444p"

    profile: Annotated[Optional[Profile],
        Option("--profile")] = \
        Field(Profile.High)
    """Features baseline, go conservative for compatibility"""

    class RateControl(str, Enum):
        ConstantQuality = "constqp"
        VariableBitrate = "vbr"
        ConstantBitrate = "cbr"

    rate_control: Annotated[Optional[RateControl],
        Option("--rc", "-r", hidden=True)] = \
        Field(RateControl.VariableBitrate)
    """Rate control mode of the bitrate"""

    rc_lookahead: Annotated[Optional[int],
        Option("--rc-lookahead", "-l", hidden=True, min=0)] = \
        Field(32, ge=0)
    """Number of frames to look ahead for the rate control"""

    cbr: Annotated[bool,
        Option("--cbr", "-c", " /--no-cbr", " /-nc", hidden=True)] = \
        Field(False)
    """Enable Constant Bitrate mode"""

    gpu: Annotated[Optional[int],
        Option("--gpu", "-g", min=-1)] = \
        Field(-1, ge=-1)
    """Use the Nth NVENC capable GPU for encoding, -1 to pick the first device available"""

    cq: Annotated[Optional[int],
        Option("--cq", "-q", min=0)] = \
        Field(25, ge=0)
    """(VBR) Similar to CRF, 0 is automatic, 1 is 'lossless', 51 is the worst quality"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:v", "h264_nvenc")
        yield every("-b:v", 0)
        yield every("-preset", denum(self.preset))
        yield every("-tune", denum(self.tune))
        yield every("-profile:v", denum(self.profile))
        yield every("-rc", denum(self.rate_control))
        yield every("-rc-lookahead", self.rc_lookahead)
        yield every("-cbr", int(self.cbr))
        yield every("-cq", self.cq)
        yield every("-gpu", self.gpu)


class FFmpegVideoCodecH264_QSV(FFmpegModuleBase):
    ... # Todo


class FFmpegVideoCodecH264_AMF(FFmpegModuleBase):
    ... # Todo


# Note: See full help with `ffmpeg -h encoder=libx265`
# https://trac.ffmpeg.org/wiki/Encode/H.265
class FFmpegVideoCodecH265(FFmpegModuleBase):
    """Encode the video with libx265"""

    crf: Annotated[Optional[int],
        Option("--crf", "-c", min=0, max=51)] = \
        Field(25, ge=0, le=51)
    """Constant Rate Factor (perceptual quality). 0 is lossless, 51 is the worst quality"""

    bitrate: Annotated[Optional[int],
        Option("--bitrate", "-b", min=0)] = \
        Field(None, ge=1)
    """Bitrate in kilobits/s"""

    class Preset(str, Enum):
        UltraFast = "ultrafast"
        SuperFast = "superfast"
        VeryFast  = "veryfast"
        Faster    = "faster"
        Fast      = "fast"
        Medium    = "medium"
        Slow      = "slow"
        Slower    = "slower"
        VerySlow  = "veryslow"

    preset: Annotated[Optional[Preset],
        Option("--preset", "-p")] = \
        Field(Preset.Slow)
    """Time to spend for better compression"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:v", "libx265")
        yield every("-preset", denum(self.preset))
        yield every("-crf", self.crf)
        yield every("-b:v", self.bitrate)


# Note: See full help with `ffmpeg -h encoder=hevc_nvenc`
# https://trac.ffmpeg.org/wiki/HWAccelIntro
class FFmpegVideoCodecH265_NVENC(FFmpegVideoCodecH265):
    """Encode the video with Nvenc h265"""

    class Preset(str, Enum):
        HighQuality2Passes        = "slow"
        HighQuality1Pass          = "medium"
        HighPerformance1Pass      = "fast"
        HighPerformance           = "hp"
        HighQuality               = "hq"
        Balanced                  = "bd"
        LowLatency                = "ll"
        LowLatencyHighQuality     = "llhq"
        LowLatencyHighPerformance = "llhp"
        Lossless                  = "lossless"
        LosslessHighPerformance   = "losslesshp"
        Fastest                   = "p1"
        Faster                    = "p2"
        Fast                      = "p3"
        Medium                    = "p4"
        Slow                      = "p5"
        Slower                    = "p6"
        Slowest                   = "p7"

    preset: Annotated[Preset,
        Option("--preset", "-p")] = \
        Field(Preset.Medium)

    class Tune(str, Enum):
        HighQuality     = "hq"
        LowLatency      = "ll"
        UltraLowLatency = "ull"
        Lossless        = "lossless"

    tune: Annotated[Optional[Tune],
        Option("--tune", "-t")] = \
        Field(Tune.HighQuality)

    class Profile(str, Enum):
        Main   = "main"
        Main10 = "main10"
        ReXT   = "rext"

    profile: Annotated[Optional[Profile],
        Option("--profile")] = \
        Field(Profile.Main)

    class Tier(str, Enum):
        Main = "main"
        High = "high"

    tier: Annotated[Optional[Tier],
        Option("--tier", "-t")] = \
        Field(Tier.High)

    class RateControl(str, Enum):
        ConstantQuality = "constqp"
        VariableBitrate = "vbr"
        ConstantBitrate = "cbr"

    rate_control: Annotated[Optional[RateControl],
        Option("--rc", "-r", hidden=True)] = \
        Field(RateControl.VariableBitrate)

    rc_lookahead: Annotated[Optional[int],
        Option("--rc-lookahead", hidden=True)] = \
        Field(10, ge=1)

    cbr: Annotated[bool,
        Option("--cbr", "-c", " /--vbr", " /-v", hidden=True)] = \
        Field(False)

    gpu: Annotated[Optional[int],
        Option("--gpu", "-g", min=-1)] = \
        Field(-1, ge=-1)
    """Use the Nth NVENC capable GPU for encoding, -1 to pick the first device available"""

    cq: Annotated[int,
        Option("--cq", "-q", min=0)] = \
        Field(25, ge=0)
    """(VBR) Similar to CRF, 0 is automatic, 1 is 'lossless', 51 is the worst quality"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:v", "hevc_nvenc")
        yield every("-preset", denum(self.preset))
        yield every("-tune", denum(self.tune))
        yield every("-profile:v", denum(self.profile))
        yield every("-tier", denum(self.tier))
        yield every("-rc", denum(self.rate_control))
        yield every("-rc-lookahead", self.rc_lookahead)
        yield every("-cbr", int(self.cbr))
        yield every("-cq", self.cq)
        yield every("-gpu", self.gpu)


class FFmpegVideoCodecH265_QSV(FFmpegModuleBase):
    ... # Todo


class FFmpegVideoCodecH265_AMF(FFmpegModuleBase):
    ... # Todo


# Note: See full help with `ffmpeg -h encoder=libsvtav1`
class FFmpegVideoCodecAV1_SVT(FFmpegModuleBase):
    """Encode the video with SVT-AV1"""

    crf: Annotated[int,
        Option("--crf", "-c", min=1, max=63)] = \
        Field(25, ge=1, le=63)
    """Constant Rate Factor (0-63), lower values mean better quality"""

    preset: Annotated[int,
        Option("--preset", "-p", min=1, max=8)] = \
        Field(3, ge=1, le=8)
    """The speed of the encoding, 0 is slowest, 8 is fastest"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:v", "libsvtav1")
        yield ("-crf", self.crf)
        yield ("-preset", self.preset)
        yield ("-svtav1-params", "tune=0")


# Note: See full help with `ffmpeg -h encoder=librav1e`
class FFmpegVideoCodecAV1_RAV1E(FFmpegModuleBase):
    """Encode the video with rav1e"""

    qp: Annotated[int,
        Option("--qp", "-q", min=-1)] = \
        Field(80, ge=-1)
    """Constant quantizer mode (from -1 to 255), smaller values are higher quality"""

    speed: Annotated[int,
        Option("--speed", "-s", min=1, max=10)] = \
        Field(4, ge=1, le=10)
    """What speed preset to use (from -1 to 10), higher is faster"""

    tile_rows: Annotated[int,
        Option("--tile-rows", "-tr", min=-1)] = \
        Field(4, ge=-1)
    """Number of tile rows to encode with (from -1 to I64_MAX)"""

    tile_columns: Annotated[int,
        Option("--tile-columns", "-tc", min=-1)] = \
        Field(4, ge=-1)
    """Number of tile columns to encode with (from -1 to I64_MAX)"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:v", "librav1e")
        yield ("-qp", self.qp)
        yield ("-speed", self.speed)
        yield ("-tile-rows", self.tile_rows)
        yield ("-tile-columns", self.tile_columns)


# Note: See full help with `ffmpeg -h encoder=av1_nvenc`
class FFmpegVideoCodecAV1_NVENC(FFmpegModuleBase):
    """Encode the video with Nvenc AV1 (RTX 4000+ GPU)"""

    class Preset(str, Enum):
        Default              = "default"
        HighQuality2Passes   = "slow"
        HighQuality1Pass     = "medium"
        HighPerformance1Pass = "fast"
        Fastest              = "p1"
        Faster               = "p2"
        Fast                 = "p3"
        Medium               = "p4"
        Slow                 = "p5"
        Slower               = "p6"
        Slowest              = "p7"

    preset: Annotated[Preset,
        Option("--preset", "-p")] = \
        Field(Preset.Slow)
    """Time to spend for better compression"""

    class Tune(str, Enum):
        HighQuality     = "hq"
        LowLatency      = "ll"
        UltraLowLatency = "ull"
        Lossless        = "lossless"

    tune: Annotated[Optional[Tune],
        Option("--tune", "-t")] = \
        Field(Tune.HighQuality)
    """Tier of performance"""

    class RateControl(str, Enum):
        ConstantQuality = "constqp"
        VariableBitrate = "vbr"
        ConstantBitrate = "cbr"

    rate_control: Annotated[Optional[RateControl],
        Option("--rc", "-r", hidden=True)] = \
        Field(RateControl.VariableBitrate)

    class Multipass(str, Enum):
        Disabled = "disabled"
        Quarter  = "qres"
        Full     = "fullres"

    multipass: Annotated[Optional[Multipass],
        Option("--multipass", "-m", hidden=True)] = \
        Field(Multipass.Full)

    tile_rows: Annotated[Optional[int],
        Option("--tile-rows", "-tr", min=1, max=64)] = \
        Field(2, ge=1, le=64)
    """Number of encoding tile rows, similar to -row-mt"""

    tile_columns: Annotated[Optional[int],
        Option("--tile-columns", "-tc", min=1, max=64)] = \
        Field(2, ge=1, le=64)
    """Number of encoding tile columns, similar to -col-mt"""

    rc_lookahead: Annotated[Optional[int],
        Option("--rc-lookahead", "-l", hidden=True)] = \
        Field(10, ge=1)
    """Number of frames to look ahead for the rate control"""

    gpu: Annotated[Optional[int],
        Option("--gpu", "-g", min=-1)] = \
        Field(-1, ge=-1)
    """Use the Nth NVENC capable GPU for encoding, -1 to pick the first device available"""

    cq: int = Field(25, ge=1)
    """Set the Constant Quality factor in a Variable Bitrate mode (similar to -crf)"""

    cq: Annotated[Optional[int],
        Option("--cq", "-q", min=0)] = \
        Field(25, ge=0)
    """Set the Constant Quality factor in a Variable Bitrate mode (similar to -crf)"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:v", "av1_nvenc")
        yield every("-preset", denum(self.preset))
        yield every("-tune", denum(self.tune))
        yield every("-rc", denum(self.rate_control))
        yield every("-rc-lookahead", self.rc_lookahead)
        yield every("-cq", self.cq)
        yield every("-gpu", self.gpu)


class FFmpegVideoCodecAV1_QSV(FFmpegModuleBase):
    ... # Todo


class FFmpegVideoCodecAV1_AMF(FFmpegModuleBase):
    ... # Todo


class FFmpegVideoCodecRawvideo(FFmpegModuleBase):
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:v", "rawvideo")


class FFmpegVideoCodecNoVideo(FFmpegModuleBase):
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:v", "null")


class FFmpegVideoCodecCopy(FFmpegModuleBase):
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:v", "copy")


FFmpegVideoCodecType: TypeAlias = Union[
    FFmpegVideoCodecH264,
    FFmpegVideoCodecH264_NVENC,
    FFmpegVideoCodecH265,
    FFmpegVideoCodecH265_NVENC,
    FFmpegVideoCodecAV1_SVT,
    FFmpegVideoCodecAV1_NVENC,
    FFmpegVideoCodecAV1_RAV1E,
    FFmpegVideoCodecRawvideo,
    FFmpegVideoCodecNoVideo,
    FFmpegVideoCodecCopy,
]

# ---------------------------------------------------------------------------- #

class FFmpegAudioCodecAAC(FFmpegModuleBase):
    """Encode the audio with Advanced Audio Codec"""

    bitrate: Annotated[int,
        Option("--bitrate", "-b", min=1)] = \
        Field(192, ge=1)
    """Bitrate in kilobits/s (shared between all audio channels)"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:a", "aac")
        yield every("-b:a", f"{self.bitrate}k")


class FFmpegAudioCodecMP3(FFmpegModuleBase):
    """Encode the audio with MP3 codec"""

    bitrate: Annotated[int,
        Option("--bitrate", "-b", min=1)] = \
        Field(192, ge=1)
    """Bitrate in kilobits/s (shared between all audio channels)"""

    qscale: Annotated[int,
        Option("--qscale", "-q", min=1)] = \
        Field(2, ge=1)
    """Quality scale, 0-9, Variable Bitrate"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:a", "libmp3lame")
        yield every("-b:a", f"{self.bitrate}k")
        yield every("-qscale:a", self.qscale)


class FFmpegAudioCodecOpus(FFmpegModuleBase):
    """Encode the audio with Opus codec"""

    bitrate: Annotated[int,
        Option("--bitrate", "-b", min=1)] = \
        Field(192, ge=1)
    """Bitrate in kilobits/s (shared between all audio channels)"""

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:a", "libopus")
        yield every("-b:a", f"{self.bitrate}k")


class FFmpegAudioCodecFLAC(FFmpegModuleBase):
    """Encode the audio with FLAC codec"""
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield every("-c:a", "flac")


class FFmpegAudioCodecCopy(FFmpegModuleBase):
    """Copy the inputs' audio streams to the output"""
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:a", "copy")


class FFmpegAudioCodecNone(FFmpegModuleBase):
    """Remove all audio tracks from the output"""
    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-an")


class FFmpegAudioCodecEmpty(FFmpegModuleBase):
    """Adds a silent stereo audio track"""
    samplerate: Annotated[float,
        Option("--samplerate", "-r", min=1)] = \
        Field(44100, ge=1)

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-f", "lavfi")
        yield ("-t", ffmpeg.time) * bool(ffmpeg.time)
        yield ("-i", f"anullsrc=channel_layout=stereo:sample_rate={self.samplerate}")


class FFmpegPCM(Enum):
    """Raw pcm formats `ffmpeg -formats | grep PCM`"""
    PCM_FLOAT_32_BITS_BIG_ENDIAN       = "pcm_f32be"
    PCM_FLOAT_32_BITS_LITTLE_ENDIAN    = "pcm_f32le"
    PCM_FLOAT_64_BITS_BIG_ENDIAN       = "pcm_f64be"
    PCM_FLOAT_64_BITS_LITTLE_ENDIAN    = "pcm_f64le"
    PCM_SIGNED_16_BITS_BIG_ENDIAN      = "pcm_s16be"
    PCM_SIGNED_16_BITS_LITTLE_ENDIAN   = "pcm_s16le"
    PCM_SIGNED_24_BITS_BIG_ENDIAN      = "pcm_s24be"
    PCM_SIGNED_24_BITS_LITTLE_ENDIAN   = "pcm_s24le"
    PCM_SIGNED_32_BITS_BIG_ENDIAN      = "pcm_s32be"
    PCM_SIGNED_32_BITS_LITTLE_ENDIAN   = "pcm_s32le"
    PCM_UNSIGNED_16_BITS_BIG_ENDIAN    = "pcm_u16be"
    PCM_UNSIGNED_16_BITS_LITTLE_ENDIAN = "pcm_u16le"
    PCM_UNSIGNED_24_BITS_BIG_ENDIAN    = "pcm_u24be"
    PCM_UNSIGNED_24_BITS_LITTLE_ENDIAN = "pcm_u24le"
    PCM_UNSIGNED_32_BITS_BIG_ENDIAN    = "pcm_u32be"
    PCM_UNSIGNED_32_BITS_LITTLE_ENDIAN = "pcm_u32le"
    PCM_UNSIGNED_8_BITS                = "pcm_u8"
    PCM_SIGNED_8_BITS                  = "pcm_s8"

    @property
    @functools.cache
    def size(self) -> int:
        return int(''.join(filter(str.isdigit, self.value)))//8

    @property
    @functools.cache
    def endian(self) -> str:
        return ("<" if ("le" in self.value) else ">")

    @property
    @functools.cache
    def dtype(self) -> np.dtype:
        return np.dtype(f"{self.endian}{self.value[4]}{self.size}")


class FFmpegAudioCodecPCM(FFmpegModuleBase):
    """Raw pcm formats `ffmpeg -formats | grep PCM`"""

    format: Annotated[FFmpegPCM,
        Option("--format", "-f")] = \
        Field(FFmpegPCM.PCM_FLOAT_32_BITS_LITTLE_ENDIAN)

    def command(self, ffmpeg: BrokenFFmpeg) -> Iterable[str]:
        yield ("-c:a", self.format.value, "-f", self.format.value.removeprefix("pcm_"))


FFmpegAudioCodecType: TypeAlias = Union[
    FFmpegAudioCodecAAC,
    FFmpegAudioCodecMP3,
    FFmpegAudioCodecOpus,
    FFmpegAudioCodecFLAC,
    FFmpegAudioCodecCopy,
    FFmpegAudioCodecNone,
    FFmpegAudioCodecEmpty,
    FFmpegAudioCodecPCM,
]

# ---------------------------------------------------------------------------- #

class FFmpegFilterBase(BaseModel, ABC):

    def __str__(self) -> str:
        return self.string()

    @abstractmethod
    def string(self) -> Iterable[str]:
        ...


class FFmpegFilterScale(FFmpegFilterBase):
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    class Resample(str, Enum):
        Bilinear   = "bilinear"
        Nearest    = "neighbor"
        Bicubic    = "bicubic"
        Gaussian   = "gauss"
        Sinc       = "sinc"
        Lanczos    = "lanczos"
        Spline     = "spline"

    resample: Annotated[Resample,
        Option("--resample", "-r")] = \
        Field(Resample.Lanczos)

    def string(self) -> str:
        return f"scale={self.width}x{self.height}:flags={denum(self.resample)}"


class FFmpegFilterVerticalFlip(FFmpegFilterBase):
    def string(self) -> str:
        return "vflip"


class FFmpegFilterCustom(FFmpegFilterBase):
    content: str

    def string(self) -> str:
        return self.content


FFmpegFilterType: TypeAlias = Union[
    FFmpegFilterScale,
    FFmpegFilterVerticalFlip,
    FFmpegFilterCustom
]

# ---------------------------------------------------------------------------- #

class BrokenFFmpeg(BaseModel):
    """Your premium FFmpeg class, serializable, sane defaults, safety"""

    # -------------------------------------------|
    # Re-export classes on BrokenFFmpeg.*

    class Input:
        Path = FFmpegInputPath
        Pipe = FFmpegInputPipe

    class Output:
        Path = FFmpegOutputPath
        Pipe = FFmpegOutputPipe

    class VideoCodec:
        H264       = FFmpegVideoCodecH264
        H264_NVENC = FFmpegVideoCodecH264_NVENC
        H265       = FFmpegVideoCodecH265
        H265_NVENC = FFmpegVideoCodecH265_NVENC
        AV1_SVT    = FFmpegVideoCodecAV1_SVT
        AV1_NVENC  = FFmpegVideoCodecAV1_NVENC
        AV1_RAV1E  = FFmpegVideoCodecAV1_RAV1E
        Rawvideo   = FFmpegVideoCodecRawvideo
        NoVideo    = FFmpegVideoCodecNoVideo
        Copy       = FFmpegVideoCodecCopy

    class AudioCodec:
        AAC   = FFmpegAudioCodecAAC
        MP3   = FFmpegAudioCodecMP3
        Opus  = FFmpegAudioCodecOpus
        FLAC  = FFmpegAudioCodecFLAC
        Copy  = FFmpegAudioCodecCopy
        None_ = FFmpegAudioCodecNone
        Empty = FFmpegAudioCodecEmpty
        PCM   = FFmpegAudioCodecPCM

    class Filter:
        Scale        = FFmpegFilterScale
        VerticalFlip = FFmpegFilterVerticalFlip
        Custom       = FFmpegFilterCustom

    # -------------------------------------------|

    hide_banner: bool = True
    """Hides compilation information"""

    shortest: bool = False
    """Ends the video at the shortest input's duration"""

    stream_loop: int = Field(0)
    """Loops the input stream N times to the right"""

    time: float = Field(0.0)
    """Stop encoding at the specified time, `-t` option of FFmpeg"""

    # https://ffmpeg.org/ffmpeg.html#Advanced-options
    vsync: Literal["auto", "passthrough", "cfr", "vfr"] = Field("cfr")
    """Framerate syncing mode"""

    class LogLevel(str, Enum):
        Error   = "error"
        Info    = "info"
        Verbose = "verbose"
        Debug   = "debug"
        Warning = "warning"
        Panic   = "panic"
        Fatal   = "fatal"

    loglevel: Annotated[LogLevel,
        Option("--loglevel", "-log")] = \
        Field(LogLevel.Error)

    class HardwareAcceleration(str, Enum):
        Auto   = "auto"
        CUDA   = "cuda"
        NVDEC  = "nvdec"
        Vulkan = "vulkan"

    # Todo: Add the required initializers on the final command per option
    # https://trac.ffmpeg.org/wiki/HWAccelIntro
    hwaccel: Annotated[Optional[HardwareAcceleration],
        Option("--hwaccel", "-hw")] = \
        Field(None)

    # https://ffmpeg.org/ffmpeg-codecs.html#toc-Codec-Options
    threads: Optional[int] = Field(None, ge=0)

    inputs: list[FFmpegInputType] = Field(default_factory=list)
    """Meta input class list"""

    filters: list[FFmpegFilterType] = Field(default_factory=list)
    """Meta filter class list"""

    outputs: list[FFmpegOutputType] = Field(default_factory=list)
    """Meta output class list"""

    vcodec: Optional[FFmpegVideoCodecType] = Field(default_factory=FFmpegVideoCodecH264)
    """The video codec to use and its configuration"""

    acodec: Optional[FFmpegAudioCodecType] = Field(None)
    """The audio codec to use and its configuration"""

    def quiet(self) -> Self:
        self.hide_banner = True
        self.loglevel = "error"
        return self

    # ---------------------------------------------------------------------------------------------|
    # Recycling

    def clear_inputs(self) -> Self:
        self.inputs = list()
        return self

    def clear_filters(self) -> Self:
        self.filters = list()
        return self

    def clear_outputs(self) -> Self:
        self.outputs = list()
        return self

    def clear_video_codec(self) -> Self:
        self.vcodec = None
        return self

    def clear_audio_codec(self) -> Self:
        self.acodec = None
        return self

    def clear(self,
        inputs: bool=True,
        filters: bool=True,
        outputs: bool=True,
        video_codec: bool=True,
        audio_codec: bool=True,
    ) -> Self:
        if inputs:      self.clear_inputs()
        if filters:     self.clear_filters()
        if outputs:     self.clear_outputs()
        if video_codec: self.clear_video_codec()
        if audio_codec: self.clear_audio_codec()
        return self

    # ---------------------------------------------------------------------------------------------|
    # Wrappers for all classes

    # Inputs and Outputs

    def add_input(self, input: FFmpegInputType) -> Self:
        self.inputs.append(input)
        return self

    @functools.wraps(FFmpegInputPath)
    def input(self, path: Path, **options) -> Self:
        return self.add_input(FFmpegInputPath(path=path, **options))

    @functools.wraps(FFmpegInputPipe)
    def pipe_input(self, **options) -> Self:
        return self.add_input(FFmpegInputPipe(**options))

    def typer_inputs(self, typer: BrokenTyper) -> None:
        with typer.panel("📦 (FFmpeg) Input"):
            typer.command(FFmpegInputPath, post=self.add_input, name="ipath")
            typer.command(FFmpegInputPipe, post=self.add_input, name="ipipe")

    def add_output(self, output: FFmpegOutputType) -> Self:
        self.outputs.append(output)
        return self

    @functools.wraps(FFmpegOutputPath)
    def output(self, path: Path, **options) -> Self:
        return self.add_output(FFmpegOutputPath(path=path, **options))

    @functools.wraps(FFmpegOutputPipe)
    def pipe_output(self, **options) -> Self:
        return self.add_output(FFmpegOutputPipe(**options))

    def typer_outputs(self, typer: BrokenTyper) -> None:
        with typer.panel("📦 (FFmpeg) Output"):
            typer.command(FFmpegOutputPath, post=self.add_output, name="opath")
            typer.command(FFmpegOutputPipe, post=self.add_output, name="opipe")

    # Video codecs

    def set_video_codec(self, codec: FFmpegVideoCodecType) -> Self:
        self.vcodec = codec
        return self

    @functools.wraps(FFmpegVideoCodecH264)
    def h264(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecH264(**options))

    @functools.wraps(FFmpegVideoCodecH264_NVENC)
    def h264_nvenc(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecH264_NVENC(**options))

    @functools.wraps(FFmpegVideoCodecH265)
    def h265(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecH265(**options))

    @functools.wraps(FFmpegVideoCodecH265_NVENC)
    def h265_nvenc(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecH265_NVENC(**options))

    @functools.wraps(FFmpegVideoCodecAV1_SVT)
    def av1_svt(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecAV1_SVT(**options))

    @functools.wraps(FFmpegVideoCodecAV1_NVENC)
    def av1_nvenc(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecAV1_NVENC(**options))

    @functools.wraps(FFmpegVideoCodecAV1_RAV1E)
    def av1_rav1e(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecAV1_RAV1E(**options))

    @functools.wraps(FFmpegVideoCodecRawvideo)
    def rawvideo(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecRawvideo(**options))

    @functools.wraps(FFmpegVideoCodecCopy)
    def copy_video(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecCopy(**options))

    @functools.wraps(FFmpegVideoCodecNoVideo)
    def no_video(self, **options) -> Self:
        return self.set_video_codec(FFmpegVideoCodecNoVideo(**options))

    def typer_vcodecs(self, typer: BrokenTyper) -> None:
        with typer.panel("📦 (Exporting) Video encoder"):
            typer.command(FFmpegVideoCodecH264,       post=self.set_video_codec, name="h264")
            typer.command(FFmpegVideoCodecH264_NVENC, post=self.set_video_codec, name="h264-nvenc")
            typer.command(FFmpegVideoCodecH265,       post=self.set_video_codec, name="h265")
            typer.command(FFmpegVideoCodecH265_NVENC, post=self.set_video_codec, name="h265-nvenc")
            typer.command(FFmpegVideoCodecAV1_SVT,    post=self.set_video_codec, name="av1-svt")
            typer.command(FFmpegVideoCodecAV1_NVENC,  post=self.set_video_codec, name="av1-nvenc")
            typer.command(FFmpegVideoCodecAV1_RAV1E,  post=self.set_video_codec, name="av1-rav1e")
            typer.command(FFmpegVideoCodecRawvideo,   post=self.set_video_codec, name="rawvideo", hidden=True)
            typer.command(FFmpegVideoCodecCopy,       post=self.set_video_codec, name="video-copy", hidden=True)
            typer.command(FFmpegVideoCodecNoVideo,    post=self.set_video_codec, name="video-none", hidden=True)

    # Audio codecs

    def set_audio_codec(self, codec: FFmpegAudioCodecType) -> Self:
        self.acodec = codec
        return self

    @functools.wraps(FFmpegAudioCodecAAC)
    def aac(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecAAC(**options))

    @functools.wraps(FFmpegAudioCodecMP3)
    def mp3(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecMP3(**options))

    @functools.wraps(FFmpegAudioCodecOpus)
    def opus(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecOpus(**options))

    @functools.wraps(FFmpegAudioCodecFLAC)
    def flac(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecFLAC(**options))

    @functools.wraps(FFmpegAudioCodecPCM)
    def pcm(self, format: FFmpegAudioCodecPCM="pcm_f32le") -> Self:
        return self.set_audio_codec(FFmpegAudioCodecPCM(format=format))

    @functools.wraps(FFmpegAudioCodecCopy)
    def copy_audio(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecCopy(**options))

    @functools.wraps(FFmpegAudioCodecNone)
    def no_audio(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecNone(**options))

    @functools.wraps(FFmpegAudioCodecEmpty)
    def empty_audio(self, **options) -> Self:
        return self.set_audio_codec(FFmpegAudioCodecEmpty(**options))

    def typer_acodecs(self, typer: BrokenTyper) -> None:
        with typer.panel("📦 (Exporting) Audio encoder"):
            typer.command(FFmpegAudioCodecAAC,   post=self.set_audio_codec, name="aac")
            typer.command(FFmpegAudioCodecMP3,   post=self.set_audio_codec, name="mp3")
            typer.command(FFmpegAudioCodecOpus,  post=self.set_audio_codec, name="opus")
            typer.command(FFmpegAudioCodecFLAC,  post=self.set_audio_codec, name="flac")
            typer.command(FFmpegAudioCodecCopy,  post=self.set_audio_codec, name="audio-copy")
            typer.command(FFmpegAudioCodecNone,  post=self.set_audio_codec, name="audio-none")
            typer.command(FFmpegAudioCodecEmpty, post=self.set_audio_codec, name="audio-empty")

    # Filters

    def add_filter(self, filter: FFmpegFilterType) -> Self:
        self.filters.append(filter)
        return self

    @functools.wraps(FFmpegFilterScale)
    def scale(self, **options) -> Self:
        return self.add_filter(FFmpegFilterScale(**options))

    @functools.wraps(FFmpegFilterVerticalFlip)
    def vflip(self, **options) -> Self:
        return self.add_filter(FFmpegFilterVerticalFlip(**options))

    @functools.wraps(FFmpegFilterCustom)
    def filter(self, content: str) -> Self:
        return self.add_filter(FFmpegFilterCustom(content=content))

    def typer_filters(self, typer: BrokenTyper) -> None:
        with typer.panel("📦 (FFmpeg) Filters"):
            typer.command(FFmpegFilterScale,        post=self.add_filter, name="scale")
            typer.command(FFmpegFilterVerticalFlip, post=self.add_filter, name="vflip")
            typer.command(FFmpegFilterCustom,       post=self.add_filter, name="filter")

    # ---------------------------------------------------------------------------------------------|
    # Command building and running

    @property
    def command(self) -> list[str]:
        if (not self.inputs):
            raise ValueError("At least one input is required for FFmpeg")
        if (not self.outputs):
            raise ValueError("At least one output is required for FFmpeg")

        command = deque()

        def extend(*objects: Union[FFmpegModuleBase, Iterable[FFmpegModuleBase]]):
            for item in flatten(objects):
                if isinstance(item, FFmpegModuleBase):
                    command.extend(flatten(item.command(self)))
                else:
                    command.append(item)

        extend("ffmpeg")
        extend("-hide_banner"*self.hide_banner)
        extend("-loglevel", denum(self.loglevel))
        extend(every("-threads", self.threads))
        extend(("-hwaccel", denum(self.hwaccel))*bool(self.hwaccel))
        extend(("-stream_loop", self.stream_loop)*bool(self.stream_loop))
        extend(self.inputs)
        extend(("-t", self.time)*bool(self.time))
        extend("-shortest"*self.shortest)

        # Note: https://trac.ffmpeg.org/wiki/Creating%20multiple%20outputs
        for output in self.outputs:
            extend(self.acodec)
            extend(self.vcodec)
            extend(every("-vf", ",".join(map(str, self.filters))))
            extend(output)

        return list(map(str, map(denum, flatten(command))))

    def run(self, **options) -> subprocess.CompletedProcess:
        return shell(self.command, **options)

    def popen(self, **options) -> subprocess.Popen:
        return shell(self.command, Popen=True, **options)

    # ---------------------------------------------------------------------------------------------|
    # High level functions

    # # Video

    @staticmethod
    def loop(path: Path, *, times: int=1, output: Path=None, echo: bool=True) -> Path:
        """Loop a video N times (1=original), output to a new file or replace the original"""
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        if (times <= 1):
            return path

        # Optional override or inline
        output = (output or path)
        looped = output.with_stem(f"{output.stem}-{times}-loops")
        logger.info(f"Looping video ({path}) {times}x times to ({output})")

        # Fastest way to loop a video, no re-encoding
        (BrokenFFmpeg(stream_loop=(times - 1)).quiet().copy_audio().copy_video()
            .input(path).output(looped, pixel_format=None).run())

        # Replace the original file or move to target
        return looped.replace(output)

    @staticmethod
    @functools.lru_cache
    def get_video_resolution(path: Path, *, echo: bool=True) -> Optional[tuple[int, int]]:
        """Get the resolution of a video in a smart way"""
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        logger.info(f"Getting Video Resolution of ({path})")
        import PIL
        return PIL.Image.open(io.BytesIO(shell(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", path, "-vframes", "1", "-f", "image2pipe", "-",
            stdout=PIPE
        ).stdout), formats=["jpeg"]).size

    @staticmethod
    def iter_video_frames(path: Path, *, skip: int=0, echo: bool=True) -> Optional[Iterable[np.ndarray]]:
        """Generator for every frame of the video as numpy arrays, FAST!"""
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        (width, height) = BrokenFFmpeg.get_video_resolution(path)
        logger.info(f"Streaming Video Frames from file ({path}) @ ({width}x{height})")
        ffmpeg = (BrokenFFmpeg(vsync="cfr")
            .quiet()
            .input(path=path)
            .filter(content=f"select='gte(n\\,{skip})'")
            .rawvideo()
            .no_audio()
            .pipe_output(
                pixel_format="rgb24",
                format="rawvideo",
            )
        ).popen(stdout=PIPE)

        # Keep reading frames until we run out, each pixel is 3 bytes !
        while (raw := ffmpeg.stdout.read(width * height * 3)):
            yield np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))

    @staticmethod
    def is_valid_video(path: Path, *, echo: bool=True) -> bool:
        if not (path := BrokenPath.get(path, exists=True)):
            return False
        return (shell(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", path, "-f", "null", "-",
            stderr=DEVNULL, stdout=DEVNULL
        ).returncode == 0)

    @staticmethod
    @functools.lru_cache
    def get_video_total_frames(path: Path, *, echo: bool=True) -> Optional[int]:
        """Count the total frames of a video by decode voiding and parsing stats output"""
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        with Halo(logger.info(f"Getting total frames of video ({path}) by decoding every frame, might take a while..")):
            return int(re.compile(r"frame=\s*(\d+)").findall((
                BrokenFFmpeg(vsync="cfr")
                .input(path=path)
                .pipe_output(format="null")
            ).run(stderr=PIPE).stderr.decode())[-1])

    @staticmethod
    @functools.lru_cache
    def get_video_duration(path: Path, *, echo: bool=True) -> Optional[float]:
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        logger.info(f"Getting Video Duration of file ({path})")
        return float(shell(
            BrokenPath.which("ffprobe"),
            "-i", path,
            "-show_entries", "format=duration",
            "-v", "quiet", "-of", "csv=p=0",
            output=True
        ))

    @staticmethod
    @functools.lru_cache
    def get_video_framerate(path: Path, *, precise: bool=False, echo: bool=True) -> Optional[float]:
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        logger.info(f"Getting Video Framerate of file ({path})")
        if precise:
            A = BrokenFFmpeg.get_video_total_frames(path)
            B = BrokenFFmpeg.get_video_duration(path)
            return (A/B)
        else:
            return float(flatten(eval(shell(
                BrokenPath.which("ffprobe"),
                "-i", path,
                "-show_entries", "stream=r_frame_rate",
                "-v", "quiet", "-of", "csv=p=0",
                output=True
            ).splitlines()[0]))[0])

    # # Audio

    @staticmethod
    @functools.lru_cache
    def get_audio_samplerate(path: Path, *, stream: int=0, echo: bool=True) -> Optional[int]:
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        logger.info(f"Getting Audio Samplerate of file ({path})")
        return int(shell(
            BrokenPath.which("ffprobe"),
            "-i", path,
            "-show_entries", "stream=sample_rate",
            "-v", "quiet", "-of", "csv=p=0",
            output=True
        ).strip().splitlines()[stream])

    @staticmethod
    @functools.lru_cache
    def get_audio_channels(path: Path, *, stream: int=0, echo: bool=True) -> Optional[int]:
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        logger.info(f"Getting Audio Channels of file ({path})")
        return int(shell(
            BrokenPath.which("ffprobe"),
            "-i", path,
            "-show_entries", "stream=channels",
            "-v", "quiet", "-of", "csv=p=0",
            output=True
        ).strip().splitlines()[stream])

    @staticmethod
    def get_audio_duration(path: Path, *, echo: bool=True) -> Optional[float]:
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        try:
            generator = BrokenAudioReader(path=path, chunk=10).stream
            while next(generator) is not None: ...
        except StopIteration as result:
            return result.value

    @staticmethod
    def get_audio_numpy(path: Path, *, echo: bool=True) -> Optional[np.ndarray]:
        if not (path := BrokenPath.get(path, exists=True)):
            return None
        logger.info(f"Getting Audio as Numpy Array of file ({path})")
        return np.concatenate(list(BrokenAudioReader(path=path, chunk=10).stream))

# ---------------------------------------------------------------------------- #
# BrokenFFmpeg Spin-offs

@define
class BrokenAudioReader:
    path: Path

    format: FFmpegPCM = FFmpegPCM.PCM_FLOAT_32_BITS_LITTLE_ENDIAN
    """The audio format to output the contents of the audio file"""

    bytes_per_sample: int = None
    """Bytes per individual sample"""

    dtype: np.dtype = None
    """Numpy dtype out of self.format"""

    channels: int = None
    """The number of audio channels in the file"""

    samplerate: int = None
    """The sample rate of the audio file"""

    chunk: float = 0.1
    """The amount of seconds to yield data at a time"""

    read: int = 0
    """Total number of bytes read from the audio file"""

    ffmpeg: Popen = None
    """The FFmpeg reader process"""

    @property
    def block_size(self) -> int:
        return (self.bytes_per_sample * self.channels)

    @property
    def bytes_per_second(self) -> int:
        return (self.block_size * self.samplerate)

    @property
    def time(self) -> float:
        return (self.read / self.bytes_per_second)

    @property
    def stream(self) -> Generator[np.ndarray, float, None]:
        if not (path := BrokenPath.get(self.path, exists=True)):
            return None
        self.path = path

        # Get audio file attributes
        self.channels   = BrokenFFmpeg.get_audio_channels(self.path)
        self.samplerate = BrokenFFmpeg.get_audio_samplerate(self.path)
        self.format = FFmpegPCM.get(self.format)
        self.bytes_per_sample = self.format.size
        self.dtype = self.format.dtype
        self.read = 0

        # Note: Stderr to null as we might not read all the audio, won't log errors
        self.ffmpeg = (
            BrokenFFmpeg()
            .quiet()
            .input(path=self.path)
            .pcm(self.format.value)
            .no_video()
            .output("-")
        ).popen(stdout=PIPE, stderr=PIPE)

        """
        The following code is wrong:

        ```python
        while (data := ffmpeg.stdout.read(chunk*samplerate)):
            yield (...)
        ```

        Reason being:
        • Small reads yields time imprecision on sample domain vs time domain
        • Must keep track of theoretical time and real time of the read
        """
        target = 0

        while True:
            target += self.chunk

            # Calculate the length of the next read to best match the target time,
            # but do not carry over temporal conversion errors
            length = (target - self.time) * self.bytes_per_second
            length = nearest(length, self.block_size, cast=int)
            length = max(length, self.block_size)
            data   = self.ffmpeg.stdout.read(length)
            if len(data) == 0: break

            # Increment precise time and read time
            yield np.frombuffer(data, dtype=self.dtype).reshape(-1, self.channels)
            self.read += len(data)

        # Allow to catch total duration on GeneratorExit
        return self.time
