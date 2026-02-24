import contextlib
import functools
import io
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from subprocess import PIPE, Popen
from typing import (
    Annotated,
    Any,
    Generator,
    Optional,
    Self,
    TypeAlias,
    Union,
)

import numpy as np
from attrs import Factory, define
from cyclopts import App, Parameter

from shaderflow import logger


def denum(item: Union[Enum, Any]) -> Any:
    if isinstance(item, Enum):
        return item.value
    return item

# Fixme: Shouldn't rely on this
def every(*items: Any) -> Iterable[Any]:
    if any(item in (None, "") for item in items):
        return []
    return items

# ---------------------------------------------------------------------------- #

@define(kw_only=True)
class FFmpegModuleBase(ABC):

    @abstractmethod
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        ...

# ---------------------------------------------------------------------------- #

@define(kw_only=True)
class FFmpegInputPath(FFmpegModuleBase):
    path: Path

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-i", self.path)


@define(kw_only=True)
class FFmpegInputPipe(FFmpegModuleBase):

    class Format(str, Enum):
        Rawvideo   = "rawvideo"
        Image2Pipe = "image2pipe"
        Null       = "null"

    format: Format = Format.Rawvideo

    class PixelFormat(str, Enum):
        YUV420P = "yuv420p"
        YUV444P = "yuv444p"
        RGB24   = "rgb24"
        RGBA    = "rgba"

    pixel_format: PixelFormat = PixelFormat.RGB24
    width: int = 1920
    height: int = 1080
    framerate: float = 60.0

    def command(self, ffmpeg: "FFmpeg") -> Iterable[str]:
        yield from ("-f", denum(self.format))
        yield from ("-s", f"{self.width}x{self.height}")
        yield from ("-pix_fmt", denum(self.pixel_format))
        yield from ("-r", self.framerate)
        yield from ("-i", "-")


FFmpegInputType: TypeAlias = Union[
    FFmpegInputPath,
    FFmpegInputPipe,
]

# ---------------------------------------------------------------------------- #

@define(kw_only=True)
class FFmpegOutputPath(FFmpegModuleBase):

    path: Path
    """Output path and extension"""

    class PixelFormat(str, Enum):
        YUV420P = "yuv420p"
        YUV444P = "yuv444p"

    pixel_format: PixelFormat = PixelFormat.YUV420P

    overwrite: bool = True

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-pix_fmt", denum(self.pixel_format))
        yield from (self.path, self.overwrite*"-y")


@define(kw_only=True)
class FFmpegOutputPipe(FFmpegModuleBase):

    class Format(str, Enum):
        Rawvideo   = "rawvideo"
        Image2Pipe = "image2pipe"
        Matroska   = "matroska"
        Mpegts     = "mpegts"
        Null       = "null"

    format: Format = Format.Mpegts

    class PixelFormat(str, Enum):
        RGB24 = "rgb24"
        RGBA  = "rgba"

    pixel_format: Optional[PixelFormat] = None

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-f", denum(self.format))
        yield from every("-pix_fmt", denum(self.pixel_format))
        yield "pipe:1"


FFmpegOutputType = Union[
    FFmpegOutputPipe,
    FFmpegOutputPath,
]

# ---------------------------------------------------------------------------- #

# Note: See full help with `ffmpeg -h encoder=h264`
# https://trac.ffmpeg.org/wiki/Encode/H.264
@define(kw_only=True)
class FFmpegVideoCodecH264(FFmpegModuleBase):
    """Encode the video with libx264"""

    class Preset(str, Enum):
        Ultrafast = "ultrafast"
        Superfast = "superfast"
        Veryfast  = "veryfast"
        Faster    = "faster"
        Fast      = "fast"
        Medium    = "medium"
        Slow      = "slow"
        Slower    = "slower"
        Veryslow  = "veryslow"

    preset: Optional[Preset] = Preset.Slow
    """Time to spend for better compression"""

    class Tune(str, Enum):
        Film        = "film"
        Animation   = "animation"
        Grain       = "grain"
        Stillimage  = "stillimage"
        Fastdecode  = "fastdecode"
        Zerolatency = "zerolatency"

    tune: Optional[Tune] = None
    """Optimize for certain types of media"""

    class Profile(str, Enum):
        Baseline = "baseline"
        Main     = "main"
        High     = "high"
        High10   = "high10"
        High422  = "high422"
        High444p = "high444p"

    profile: Optional[Profile] = None
    """Features baseline, go conservative for compatibility"""

    crf: int = 20
    """Constant Rate Factor, 0 is lossless, 51 is the worst quality"""

    bitrate: Optional[int] = None
    """Bitrate in kilobits/s, the higher the better quality and file size"""

    x264params: Annotated[list[str], Parameter(negative=False)] = []
    """Additional options to pass to x264"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:v", "libx264")
        yield from every("-movflags", "+faststart")
        yield from every("-profile", denum(self.profile))
        yield from every("-preset", denum(self.preset))
        yield from every("-tune", denum(self.tune))
        yield from every("-b:v", self.bitrate)
        yield from every("-crf", self.crf)
        yield from every("-x264opts", ":".join(self.x264params or []))


# Note: See full help with `ffmpeg -h encoder=h264_nvenc`
@define(kw_only=True)
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

    preset: Optional[Preset] = Preset.Medium
    """Time to spend for better compression"""

    class Tune(str, Enum):
        HighQuality     = "hq"
        LowLatency      = "ll"
        UltraLowLatency = "ull"
        Lossless        = "lossless"

    tune: Optional[Tune] = Tune.HighQuality
    """Tune the encoder for a specific tier of performance"""

    class Profile(str, Enum):
        Baseline = "baseline"
        Main     = "main"
        High     = "high"
        High444p = "high444p"

    profile: Optional[Profile] = Profile.High
    """Features baseline, go conservative for compatibility"""

    class RateControl(str, Enum):
        ConstantQuality = "constqp"
        VariableBitrate = "vbr"
        ConstantBitrate = "cbr"

    rate_control: Optional[RateControl] = RateControl.VariableBitrate
    """Rate control mode of the bitrate"""

    rc_lookahead: Optional[int] = 32
    """Number of frames to look ahead for the rate control"""

    cbr: bool = False
    """Enable Constant Bitrate mode"""

    gpu: Optional[int] = -1
    """Use the Nth NVENC capable GPU for encoding, -1 to pick the first device available"""

    cq: Optional[int] = 25
    """(VBR) Similar to CRF, 0 is automatic, 1 is 'lossless', 51 is the worst quality"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:v", "h264_nvenc")
        yield from every("-b:v", 0)
        yield from every("-preset", denum(self.preset))
        yield from every("-tune", denum(self.tune))
        yield from every("-profile:v", denum(self.profile))
        yield from every("-rc", denum(self.rate_control))
        yield from every("-rc-lookahead", self.rc_lookahead)
        yield from every("-cbr", int(self.cbr))
        yield from every("-cq", self.cq)
        yield from every("-gpu", self.gpu)


@define(kw_only=True)
class FFmpegVideoCodecH264_QSV(FFmpegModuleBase):
    ... # Todo


@define(kw_only=True)
class FFmpegVideoCodecH264_AMF(FFmpegModuleBase):
    ... # Todo


# Note: See full help with `ffmpeg -h encoder=libx265`
# https://trac.ffmpeg.org/wiki/Encode/H.265
@define(kw_only=True)
class FFmpegVideoCodecH265(FFmpegModuleBase):
    """Encode the video with libx265"""

    crf: Optional[int] = 25
    """Constant Rate Factor (perceptual quality). 0 is lossless, 51 is the worst quality"""

    bitrate: Optional[int] = None
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

    preset: Optional[Preset] = Preset.Slow
    """Time to spend for better compression"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:v", "libx265")
        yield from every("-preset", denum(self.preset))
        yield from every("-crf", self.crf)
        yield from every("-b:v", self.bitrate)


# Note: See full help with `ffmpeg -h encoder=hevc_nvenc`
# https://trac.ffmpeg.org/wiki/HWAccelIntro
@define(kw_only=True)
class FFmpegVideoCodecH265_NVENC(FFmpegModuleBase):
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

    preset: Preset = Preset.Medium

    class Tune(str, Enum):
        HighQuality     = "hq"
        LowLatency      = "ll"
        UltraLowLatency = "ull"
        Lossless        = "lossless"

    tune: Optional[Tune] = Tune.HighQuality

    class Profile(str, Enum):
        Main   = "main"
        Main10 = "main10"
        ReXT   = "rext"

    profile: Optional[Profile] = Profile.Main

    class Tier(str, Enum):
        Main = "main"
        High = "high"

    tier: Optional[Tier] = Tier.High

    class RateControl(str, Enum):
        ConstantQuality = "constqp"
        VariableBitrate = "vbr"
        ConstantBitrate = "cbr"

    rate_control: Optional[RateControl] = RateControl.VariableBitrate

    rc_lookahead: Optional[int] = 10

    cbr: bool = False

    gpu: Optional[int] = -1
    """Use the Nth NVENC capable GPU for encoding, -1 to pick the first device available"""

    cq: int = 25
    """(VBR) Similar to CRF, 0 is automatic, 1 is 'lossless', 51 is the worst quality"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:v", "hevc_nvenc")
        yield from every("-preset", denum(self.preset))
        yield from every("-tune", denum(self.tune))
        yield from every("-profile:v", denum(self.profile))
        yield from every("-tier", denum(self.tier))
        yield from every("-rc", denum(self.rate_control))
        yield from every("-rc-lookahead", self.rc_lookahead)
        yield from every("-cbr", int(self.cbr))
        yield from every("-cq", self.cq)
        yield from every("-gpu", self.gpu)


@define(kw_only=True)
class FFmpegVideoCodecH265_QSV(FFmpegModuleBase):
    ... # Todo


@define(kw_only=True)
class FFmpegVideoCodecH265_AMF(FFmpegModuleBase):
    ... # Todo


# Note: See full help with `ffmpeg -h encoder=libsvtav1`
@define(kw_only=True)
class FFmpegVideoCodecAV1_SVT(FFmpegModuleBase):
    """Encode the video with SVT-AV1"""

    crf: int = 25
    """Constant Rate Factor (0-63), lower values mean better quality"""

    preset: int = 3
    """The speed of the encoding, 0 is slowest, 8 is fastest"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:v", "libsvtav1")
        yield from ("-crf", self.crf)
        yield from ("-preset", self.preset)
        yield from ("-svtav1-params", "tune=0")


# Note: See full help with `ffmpeg -h encoder=librav1e`
@define(kw_only=True)
class FFmpegVideoCodecAV1_RAV1E(FFmpegModuleBase):
    """Encode the video with rav1e"""

    qp: int = 80
    """Constant quantizer mode (from -1 to 255), smaller values are higher quality"""

    speed: int = 4
    """What speed preset to use (from 1 to 10), higher is faster"""

    tile_rows: int = 4
    """Number of tile rows to encode with (from -1 to I64_MAX)"""

    tile_columns: int = 4
    """Number of tile columns to encode with (from -1 to I64_MAX)"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:v", "librav1e")
        yield from ("-qp", self.qp)
        yield from ("-speed", self.speed)
        yield from ("-tile-rows", self.tile_rows)
        yield from ("-tile-columns", self.tile_columns)


# Note: See full help with `ffmpeg -h encoder=av1_nvenc`
@define(kw_only=True)
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

    preset: Preset = Preset.Slow
    """Time to spend for better compression"""

    class Tune(str, Enum):
        HighQuality     = "hq"
        LowLatency      = "ll"
        UltraLowLatency = "ull"
        Lossless        = "lossless"

    tune: Optional[Tune] = Tune.HighQuality

    class RateControl(str, Enum):
        ConstantQuality = "constqp"
        VariableBitrate = "vbr"
        ConstantBitrate = "cbr"

    rc: Optional[RateControl] = RateControl.VariableBitrate

    class Multipass(str, Enum):
        Disabled = "disabled"
        Quarter  = "qres"
        Full     = "fullres"

    multipass: Optional[Multipass] = Multipass.Disabled

    tile_rows: Optional[int] = 2
    """Number of encoding tile rows, similar to -row-mt"""

    tile_columns:Optional[int] = 2
    """Number of encoding tile columns, similar to -col-mt"""

    rc_lookahead: Optional[int] = 10
    """Number of frames to look ahead for the rate control"""

    gpu: Optional[int] = -1
    """Use the Nth NVENC capable GPU for encoding, -1 to pick the first device available"""

    cq: int = 25
    """Set the Constant Quality factor in a Variable Bitrate mode (similar to -crf)"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:v", "av1_nvenc")
        yield from every("-preset", denum(self.preset))
        yield from every("-tune", denum(self.tune))
        yield from every("-rc", denum(self.rc))
        yield from every("-rc-lookahead", self.rc_lookahead)
        yield from every("-cq", self.cq)
        yield from every("-gpu", self.gpu)


@define(kw_only=True)
class FFmpegVideoCodecAV1_QSV(FFmpegModuleBase):
    ... # Todo


@define(kw_only=True)
class FFmpegVideoCodecAV1_AMF(FFmpegModuleBase):
    ... # Todo


@define(kw_only=True)
class FFmpegVideoCodecRawvideo(FFmpegModuleBase):
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:v", "rawvideo")


@define(kw_only=True)
class FFmpegVideoCodecNoVideo(FFmpegModuleBase):
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:v", "null")


@define(kw_only=True)
class FFmpegVideoCodecCopy(FFmpegModuleBase):
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:v", "copy")


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

@define(kw_only=True)
class FFmpegAudioCodecAAC(FFmpegModuleBase):
    """Encode the audio with Advanced Audio Codec"""

    bitrate: int = 192
    """Bitrate in kilobits/s (shared between all audio channels)"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:a", "aac")
        yield from every("-b:a", f"{self.bitrate}k")


@define(kw_only=True)
class FFmpegAudioCodecMP3(FFmpegModuleBase):
    """Encode the audio with MP3 codec"""

    bitrate: int = 192
    """Bitrate in kilobits/s (shared between all audio channels)"""

    qscale: int = 2
    """Quality scale, 0-9, Variable Bitrate"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:a", "libmp3lame")
        yield from every("-b:a", f"{self.bitrate}k")
        yield from every("-qscale:a", self.qscale)


@define(kw_only=True)
class FFmpegAudioCodecOpus(FFmpegModuleBase):
    """Encode the audio with Opus codec"""

    bitrate: int = 192
    """Bitrate in kilobits/s (shared between all audio channels)"""

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:a", "libopus")
        yield from every("-b:a", f"{self.bitrate}k")


@define(kw_only=True)
class FFmpegAudioCodecFLAC(FFmpegModuleBase):
    """Encode the audio with FLAC codec"""
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from every("-c:a", "flac")


@define(kw_only=True)
class FFmpegAudioCodecCopy(FFmpegModuleBase):
    """Copy the inputs' audio streams to the output"""
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:a", "copy")


@define(kw_only=True)
class FFmpegAudioCodecNone(FFmpegModuleBase):
    """Remove all audio tracks from the output"""
    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield "-an"


@define(kw_only=True)
class FFmpegAudioCodecEmpty(FFmpegModuleBase):
    """Adds a silent stereo audio track"""
    samplerate: int = 44100

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-f", "lavfi")
        yield from ("-t", ffmpeg.time) * bool(ffmpeg.time)
        yield from ("-i", f"anullsrc=channel_layout=stereo:sample_rate={self.samplerate}")


class FFmpegPCM(str, Enum):
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


@define(kw_only=True)
class FFmpegAudioCodecPCM(FFmpegModuleBase):
    """Raw pcm formats `ffmpeg -formats | grep PCM`"""

    format: FFmpegPCM = FFmpegPCM.PCM_FLOAT_32_BITS_LITTLE_ENDIAN

    def command(self, ffmpeg: 'FFmpeg') -> Iterable[str]:
        yield from ("-c:a", self.format.value)
        yield from ("-f", self.format.value.removeprefix("pcm_"))


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

@define(kw_only=True)
class FFmpegFilterBase(ABC):

    def __str__(self) -> str:
        return self.string()

    @abstractmethod
    def string(self) -> Iterable[str]:
        ...


@define(kw_only=True)
class FFmpegFilterScale(FFmpegFilterBase):
    width: int
    height: int

    class Resample(str, Enum):
        Bilinear   = "bilinear"
        Nearest    = "neighbor"
        Bicubic    = "bicubic"
        Gaussian   = "gauss"
        Sinc       = "sinc"
        Lanczos    = "lanczos"
        Spline     = "spline"

    resample: Resample = Resample.Lanczos

    def string(self) -> str:
        return f"scale={self.width}x{self.height}:flags={denum(self.resample)}"


@define(kw_only=True)
class FFmpegFilterVerticalFlip(FFmpegFilterBase):
    def string(self) -> str:
        return "vflip"


@define(kw_only=True)
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

@define(kw_only=True)
class FFmpeg:

    hide_banner: bool = True
    """Hides compilation information"""

    shortest: bool = False
    """Ends the video at the shortest input's duration"""

    stream_loop: int = 0
    """Loops the input stream N times to the right"""

    time: Optional[float] = None
    """Stop encoding at the specified time, `-t` option of FFmpeg"""

    class VsyncMode(str, Enum):
        Auto = "auto"
        Pass = "passthrough"
        CFR  = "cfr"
        VFR  = "vfr"

    # https://ffmpeg.org/ffmpeg.html#Advanced-options
    vsync: VsyncMode = VsyncMode.CFR
    """Framerate syncing mode"""

    class LogLevel(str, Enum):
        Error   = "error"
        Info    = "info"
        Verbose = "verbose"
        Debug   = "debug"
        Warning = "warning"
        Panic   = "panic"
        Fatal   = "fatal"

    loglevel: LogLevel = LogLevel.Error

    class HardwareAcceleration(str, Enum):
        Auto   = "auto"
        CUDA   = "cuda"
        NVDEC  = "nvdec"
        Vulkan = "vulkan"

    # Todo: Add the required initializers on the final command per option
    # https://trac.ffmpeg.org/wiki/HWAccelIntro
    hwaccel: Optional[HardwareAcceleration] = None

    inputs: list[FFmpegInputType] = []
    """Meta input class list"""

    filters: list[FFmpegFilterType] = []
    """Meta filter class list"""

    outputs: list[FFmpegOutputType] = []
    """Meta output class list"""

    vcodec: Optional[FFmpegVideoCodecType] = Factory(FFmpegVideoCodecH264)
    """The video codec to use and its configuration"""

    acodec: Optional[FFmpegAudioCodecType] = None
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

    def smartset(self, object: Any) -> Self:
        if isinstance(object, FFmpegInputType):
            self.inputs.append(object)
        elif isinstance(object, FFmpegFilterType):
            self.filters.append(object)
        elif isinstance(object, FFmpegOutputType):
            self.outputs.append(object)
        elif isinstance(object, FFmpegVideoCodecType):
            self.vcodec = object
        elif isinstance(object, FFmpegAudioCodecType):
            self.acodec = object
        else:
            raise TypeError(f"Unsupported type: {type(object)}")
        return self

    # ---------------------------------------------------------------------------------------------|
    # Wrappers for all classes

    # Inputs and Outputs

    @functools.wraps(FFmpegInputPath)
    def input(self, path: Path, **options) -> Self:
        return self.add_input(FFmpegInputPath(path=path, **options))

    @functools.wraps(FFmpegInputPipe)
    def pipe_input(self, **options) -> Self:
        return self.add_input(FFmpegInputPipe(**options))

    def cli_inputs(self, app: App) -> None:
        with contextlib.nullcontext("📦 (FFmpeg) Input") as group:
            app.command(FFmpegInputPath, name="ipath", group=group, result_action=self.inputs.append)
            app.command(FFmpegInputPipe, name="ipipe", group=group, result_action=self.inputs.append)

    @functools.wraps(FFmpegOutputPath)
    def output(self, path: Path, **options) -> Self:
        return self.add_output(FFmpegOutputPath(path=path, **options))

    @functools.wraps(FFmpegOutputPipe)
    def pipe_output(self, **options) -> Self:
        return self.add_output(FFmpegOutputPipe(**options))

    def cli_outputs(self, app: App) -> None:
        with contextlib.nullcontext("📦 (FFmpeg) Output") as group:
            app.command(FFmpegOutputPath, name="opath", group=group, result_action=self.outputs.append)
            app.command(FFmpegOutputPipe, name="opipe", group=group, result_action=self.outputs.append)

    # Video codecs

    @functools.wraps(FFmpegVideoCodecH264)
    def h264(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecH264(**options))

    @functools.wraps(FFmpegVideoCodecH264_NVENC)
    def h264_nvenc(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecH264_NVENC(**options))

    @functools.wraps(FFmpegVideoCodecH265)
    def h265(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecH265(**options))

    @functools.wraps(FFmpegVideoCodecH265_NVENC)
    def h265_nvenc(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecH265_NVENC(**options))

    @functools.wraps(FFmpegVideoCodecAV1_SVT)
    def av1_svt(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecAV1_SVT(**options))

    @functools.wraps(FFmpegVideoCodecAV1_NVENC)
    def av1_nvenc(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecAV1_NVENC(**options))

    @functools.wraps(FFmpegVideoCodecAV1_RAV1E)
    def av1_rav1e(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecAV1_RAV1E(**options))

    @functools.wraps(FFmpegVideoCodecRawvideo)
    def rawvideo(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecRawvideo(**options))

    @functools.wraps(FFmpegVideoCodecCopy)
    def copy_video(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecCopy(**options))

    @functools.wraps(FFmpegVideoCodecNoVideo)
    def no_video(self, **options) -> Self:
        return self.smartset(FFmpegVideoCodecNoVideo(**options))

    def cli_vcodecs(self, app: App) -> None:
        with contextlib.nullcontext("📦 (Exporting) Video encoder") as group:
            app.command(FFmpegVideoCodecH264,       name="h264",       group=group, result_action=self.smartset)
            app.command(FFmpegVideoCodecH264_NVENC, name="h264-nvenc", group=group, result_action=self.smartset)
            app.command(FFmpegVideoCodecH265,       name="h265",       group=group, result_action=self.smartset)
            app.command(FFmpegVideoCodecH265_NVENC, name="h265-nvenc", group=group, result_action=self.smartset)
            app.command(FFmpegVideoCodecAV1_SVT,    name="av1-svt",    group=group, result_action=self.smartset)
            app.command(FFmpegVideoCodecAV1_NVENC,  name="av1-nvenc",  group=group, result_action=self.smartset)
            app.command(FFmpegVideoCodecAV1_RAV1E,  name="av1-rav1e",  group=group, result_action=self.smartset)

    # Audio codecs

    @functools.wraps(FFmpegAudioCodecAAC)
    def aac(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecAAC(**options))

    @functools.wraps(FFmpegAudioCodecMP3)
    def mp3(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecMP3(**options))

    @functools.wraps(FFmpegAudioCodecOpus)
    def opus(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecOpus(**options))

    @functools.wraps(FFmpegAudioCodecFLAC)
    def flac(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecFLAC(**options))

    @functools.wraps(FFmpegAudioCodecPCM)
    def pcm(self, format: FFmpegAudioCodecPCM="pcm_f32le") -> Self:
        return self.smartset(FFmpegAudioCodecPCM(format=format))

    @functools.wraps(FFmpegAudioCodecCopy)
    def copy_audio(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecCopy(**options))

    @functools.wraps(FFmpegAudioCodecNone)
    def no_audio(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecNone(**options))

    @functools.wraps(FFmpegAudioCodecEmpty)
    def empty_audio(self, **options) -> Self:
        return self.smartset(FFmpegAudioCodecEmpty(**options))

    def cli_acodecs(self, app: App) -> None:
        with contextlib.nullcontext("📦 (Exporting) Audio encoder") as group:
            app.command(FFmpegAudioCodecAAC,   name="aac",    group=group, result_action=self.smartset)
            app.command(FFmpegAudioCodecMP3,   name="mp3",    group=group, result_action=self.smartset)
            app.command(FFmpegAudioCodecOpus,  name="opus",   group=group, result_action=self.smartset)
            app.command(FFmpegAudioCodecFLAC,  name="flac",   group=group, result_action=self.smartset)
            app.command(FFmpegAudioCodecCopy,  name="acopy",  group=group, result_action=self.smartset)
            app.command(FFmpegAudioCodecNone,  name="anone",  group=group, result_action=self.smartset)
            app.command(FFmpegAudioCodecEmpty, name="aempty", group=group, result_action=self.smartset)

    # Filters

    @functools.wraps(FFmpegFilterScale)
    def scale(self, **options) -> Self:
        return self.smartset(FFmpegFilterScale(**options))

    @functools.wraps(FFmpegFilterVerticalFlip)
    def vflip(self, **options) -> Self:
        return self.smartset(FFmpegFilterVerticalFlip(**options))

    @functools.wraps(FFmpegFilterCustom)
    def filter(self, content: str) -> Self:
        return self.smartset(FFmpegFilterCustom(content=content))

    def cli_filters(self, app: App) -> None:
        with contextlib.nullcontext("📦 (FFmpeg) Filters") as group:
            app.command(FFmpegFilterScale,        name="scale",  group=group, result_action=self.smartset)
            app.command(FFmpegFilterVerticalFlip, name="vflip",  group=group, result_action=self.smartset)
            app.command(FFmpegFilterCustom,       name="filter", group=group, result_action=self.smartset)

    # ---------------------------------------------------------------------------------------------|
    # Command building and running

    @property
    def command(self) -> tuple[str]:
        if (not self.inputs):
            raise ValueError("At least one input is required for FFmpeg")
        if (not self.outputs):
            raise ValueError("At least one output is required for FFmpeg")

        command = deque()
        command.append(shutil.which("ffmpeg"))

        if self.hide_banner:
            command.extend(("-hide_banner",) * self.hide_banner)

        command.extend(("-loglevel", denum(self.loglevel)))

        if self.hwaccel is not None:
            command.extend(("-hwaccel", denum(self.hwaccel)))

        if self.stream_loop > 0:
            command.extend(("-stream_loop", self.stream_loop))

        for item in self.inputs:
            command.extend(item.command(self))

        if self.time is not None:
            command.extend(("-t", self.time))

        if self.shortest:
            command.append("-shortest")

        # Note: https://trac.ffmpeg.org/wiki/Creating%20multiple%20outputs
        for output in self.outputs:
            if self.acodec is not None:
                command.extend(self.acodec.command(self))
            if self.vcodec is not None:
                command.extend(self.vcodec.command(self))

            if len(self.filters) > 0:
                command.extend(("-vf", ",".join(map(str, self.filters))))

            command.extend(output.command(self))

        return tuple(map(str, command))

    def run(self, **options) -> subprocess.CompletedProcess:
        return subprocess.run(self.command, **options)

    def popen(self, **options) -> subprocess.Popen:
        logger.info(f"Call {tuple(self.command)}")
        return subprocess.Popen(self.command, **options)

    # ---------------------------------------------------------------------------------------------|
    # High level functions

    # # Video

    @staticmethod
    def loop(path: Path, *, times: int=1, output: Path=None, echo: bool=True) -> Path:
        """Loop a video N times (1=original), output to a new file or replace the original"""
        if (path is None) or not (path := Path(path)).exists():
            return None
        if (times <= 1):
            return path

        # Optional override or inline
        output = (output or path)
        looped = output.with_stem(f"{output.stem}-{times}-loops")
        logger.info(f"Looping video ({path}) {times}x times to ({output})")

        # Fastest way to loop a video, no re-encoding
        (FFmpeg(stream_loop=(times - 1)).quiet().copy_audio().copy_video()
            .input(path).output(looped, pixel_format=None).run())

        # Replace the original file or move to target
        return looped.replace(output)

    @staticmethod
    @functools.lru_cache
    def get_video_resolution(path: Path, *, echo: bool=True) -> Optional[tuple[int, int]]:
        """Get the resolution of a video in a smart way"""
        if (path is None) or not (path := Path(path)).exists():
            return None
        logger.info(f"Getting Video Resolution of ({path})")
        import PIL
        return PIL.Image.open(io.BytesIO(subprocess.run((
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", path, "-vframes", "1", "-f", "image2pipe", "-",
        ), stdout=PIPE).stdout), formats=["jpeg"]).size

    @staticmethod
    def iter_video_frames(path: Path, *, skip: int=0, echo: bool=True) -> Optional[Iterable[np.ndarray]]:
        """Generator for every frame of the video as numpy arrays, FAST!"""
        if (path is None) or not (path := Path(path)).exists():
            return None
        (width, height) = FFmpeg.get_video_resolution(path)
        logger.info(f"Streaming Video Frames from file ({path}) @ ({width}x{height})")
        ffmpeg = (FFmpeg(vsync="cfr")
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
        if (path is None) or not (path := Path(path)).exists():
            return None
        return (subprocess.run((
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", path, "-f", "null", "-"
        )).returncode == 0)

    @staticmethod
    @functools.lru_cache
    def get_video_total_frames(path: Path, *, echo: bool=True) -> Optional[int]:
        """Count the total frames of a video by decode voiding and parsing stats output"""
        if (path is None) or not (path := Path(path)).exists():
            return None
        logger.info(f"Getting total frames ({path}), might take a while..")
        return int(re.compile(r"frame=\s*(\d+)").findall((
            FFmpeg(vsync="cfr")
            .input(path=path)
            .pipe_output(format="null")
        ).run(stderr=PIPE).stderr.decode())[-1])

    @staticmethod
    @functools.lru_cache
    def get_video_duration(path: Path, *, echo: bool=True) -> Optional[float]:
        if (path is None) or not (path := Path(path)).exists():
            return None
        logger.info(f"Getting Video Duration of file ({path})")
        return eval(subprocess.check_output((
            "ffprobe",
            "-i", path,
            "-show_entries", "format=duration",
            "-v", "quiet", "-of", "csv=p=0",
        )).decode().strip())

    @staticmethod
    @functools.lru_cache
    def get_video_framerate(path: Path, *, precise: bool=False, echo: bool=True) -> Optional[float]:
        if (path is None) or not (path := Path(path)).exists():
            return None
        logger.info(f"Getting Video Framerate of file ({path})")
        if precise:
            A = FFmpeg.get_video_total_frames(path)
            B = FFmpeg.get_video_duration(path)
            return (A/B)
        else:
            return eval(subprocess.check_output((
                "ffprobe", "-hide_banner", "-loglevel", "error",
                "-of", "default=noprint_wrappers=1:nokey=1",
                "-show_entries", "stream=r_frame_rate",
                "-select_streams", "v:0",
                "-i", path,
            )).decode().strip())

    # # Audio

    @staticmethod
    @functools.lru_cache
    def get_audio_samplerate(path: Path, *, stream: int=0, echo: bool=True) -> Optional[int]:
        if (path is None) or not (path := Path(path)).exists():
            return None
        logger.info(f"Getting Audio Samplerate of file ({path})")
        return eval(subprocess.check_output((
            "ffprobe",
            "-show_entries", "stream=sample_rate",
            "-v", "quiet", "-of", "csv=p=0",
            "-i", str(path),
        )).decode().strip().splitlines()[stream])

    @staticmethod
    @functools.lru_cache
    def get_audio_channels(path: Path, *, stream: int=0, echo: bool=True) -> Optional[int]:
        if (path is None) or not (path := Path(path)).exists():
            return None
        logger.info(f"Getting Audio Channels of file ({path})")
        return eval(subprocess.check_output((
            "ffprobe",
            "-i", str(path),
            "-show_entries", "stream=channels",
            "-v", "quiet", "-of", "csv=p=0",
        )).decode().strip().splitlines()[stream])

    @staticmethod
    def get_audio_duration(path: Path, *, echo: bool=True) -> Optional[float]:
        if (path is None) or not (path := Path(path)).exists():
            return None
        try:
            generator = BrokenAudioReader(path=path, chunk=10).stream
            while next(generator) is not None: ...
        except StopIteration as result:
            return result.value

    @staticmethod
    def get_audio_numpy(path: Path, *, echo: bool=True) -> Optional[np.ndarray]:
        if (path is None) or not (path := Path(path)).exists():
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
        if self.path is None:
            return None

        # Get audio file attributes
        self.channels   = FFmpeg.get_audio_channels(self.path)
        self.samplerate = FFmpeg.get_audio_samplerate(self.path)
        self.format = FFmpegPCM(self.format)
        self.bytes_per_sample = self.format.size
        self.dtype = self.format.dtype
        self.read = 0

        # Note: Stderr to null as we might not read all the audio, won't log errors
        self.ffmpeg = (
            FFmpeg()
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
            length = int(self.block_size * round(length / self.block_size))
            length = max(length, self.block_size)
            data   = self.ffmpeg.stdout.read(length)
            if len(data) == 0: break

            # Increment precise time and read time
            yield np.frombuffer(data, dtype=self.dtype).reshape(-1, self.channels)
            self.read += len(data)

        # Allow to catch total duration on GeneratorExit
        return self.time
