from . import *


@define(slots=False)
class BrokenSmartVideoFrames(BrokenAttrs):
    path:     PathLike = None
    buffer:   Seconds  = 60
    threads:  int      = 6
    quality:  int      = 95
    time:     Seconds  = 0
    lossless: bool     = True
    _width:   int      = None
    _height:  int      = None
    _fps:     Hertz    = None
    _turbo:   Any      = None
    _raw:     deque    = Factory(deque)
    _frames:  Dict     = Factory(dict)

    # Dynamically set
    encode:  Callable = None
    decode:  Callable = None

    @property
    def max_raw(self) -> int:
        return self.threads*4

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    # # Initialization

    LOSSLESS_MAX_BUFFER_LENGTH = 4

    def __post__(self):
        self._fps = BrokenFFmpeg.get_framerate(self.path)
        self._width, self._height = BrokenFFmpeg.get_resolution(self.path)

        if not all((self._fps, self._width, self._height)):
            raise ValueError("Could not get video metadata")

        # TurboJPEG will raise if shared lib is not found
        with contextlib.suppress(RuntimeError):
            self._turbo = turbojpeg.TurboJPEG()

        if self.lossless:
            log.warning(f"Using lossless frames. Limiting buffer length for Out of Memory safety")
            self.buffer = min(self.buffer, BrokenSmartVideoFrames.LOSSLESS_MAX_BUFFER_LENGTH)
            self.encode = lambda frame: frame
            self.decode = lambda frame: frame

        elif (self._turbo is not None):
            log.success(f"Using TurboJPEG for compression. Best speeds available")
            self.encode = lambda frame: self._turbo.encode(frame, quality=self.quality)
            self.decode = lambda frame: self._turbo.decode(frame)

        elif BrokenUtils.have_import("cv2"):
            log.success(f"Using OpenCV for compression. Slower than TurboJPEG but enough")
            self.encode = lambda frame: cv2.imencode(".jpeg", frame)[1]
            self.decode = lambda frame: cv2.imdecode(frame, cv2.IMREAD_COLOR)

        else:
            log.warning(f"Using PIL for compression. Performance killer GIL fallback")
            self.decode = lambda frame: PIL.Image.open(BytesIO(frame))
            self.encode = lambda frame: PIL.Image.fromarray(frame).save(
                BytesIO(), format="jpeg", quality=self.quality
            )

        # Create worker threads. The good, the bad and the ugly
        BrokenThread(target=self.extractor, daemon=True)
        BrokenThread(target=self.deleter,  daemon=True)
        for _ in range(self.threads):
            BrokenThread(target=self.worker, daemon=True)

    # # Utilities

    def time2index(self, time: Seconds) -> int:
        return int(time*self._fps)

    def index2time(self, index: int) -> Seconds:
        return (index/self._fps)

    # # Check if we can decode and encode with the libraries

    def get_frame(self, time: Seconds) -> Tuple[int, numpy.ndarray]:
        want = self.time2index(time)
        self.time = time
        import time

        # Wait until the frame exists
        while (jpeg := self._frames.get(want)) is None:
            time.sleep(0.01)

        return (want, lambda: self.decode(jpeg))

    @property
    def buffer_frames(self) -> int:
        return int(self.buffer*self._fps)

    @property
    def time_index(self) -> int:
        return self.time2index(self.time)

    @property
    def _future_index(self) -> int:
        return self.time_index + self.buffer_frames

    def _future_window(self, index: int) -> bool:
        return index < self._future_index

    @property
    def _past_index(self) -> int:
        return self.time_index - self.buffer_frames

    def _past_window(self, index: int) -> bool:
        return self._past_index < index

    def _time_window(self, index: int) -> bool:
        return self._past_window(index) and self._future_window(index)

    def _should_rewind(self, index: int) -> bool:
        """Point must be older than the past cutoff to trigger a rewind"""
        return (self.time_index + self.buffer_frames) < index

    # # Workers

    _oldest: int = 0
    _newest: int = 0

    def extractor(self):
        def forward():
            for index, frame in enumerate(BrokenFFmpeg.get_frames(self.path)):

                # Skip already processed frames
                if self._frames.get(index) is not None:
                    continue

                # Skip frames outside of the past time window
                if not self._past_window(index):
                    continue

                while not self._future_window(index):
                    if self._should_rewind(index):
                        return
                    time.sleep(0.01)

                # Limit how much raw frames there can be
                while len(self._raw) > self.max_raw:
                    time.sleep(0.01)

                self._raw.append((index, frame))
                self._newest = max(self._newest, index)

        while True:
            forward()

    def worker(self):
        """Blindly get new frames from the deque, compress and store them"""
        while True:
            try:
                index, frame = self._raw.popleft()
                frame = numpy.array(numpy.flip(frame, axis=0))
                self._frames[index] = self.encode(frame)
            except IndexError:
                time.sleep(0.01)

    def deleter(self):
        """Delete old frames that are not in the time window"""
        while True:
            for index in range(self._oldest, self._past_index):
                self._frames[index] = None
                self._oldest = index
            for index in range(self._newest, self._future_index, -1):
                self._frames[index] = None
                self._newest = index
            time.sleep(0.5)

# -------------------------------------------------------------------------------------------------|

@define
class VideoTexture(BrokenSmartVideoFrames, Module):
    name:    str     = "iVideo"
    texture: Texture = None
    layers:  int     = 30

    def __post__(self):
        self.texture = Texture(
            scene=self.scene,
            name=self.name,
            width=self.width,
            height=self.height,
            layers=self.layers,
            rolling=True,
            components=3,
        )

    _previous: int = 0

    def update(self):
        index, decode = self.get_frame(self.scene.time)

        # Skip if the frame is the same
        if index != self._previous:
            self._previous = index
            self.texture.roll()
            self.texture.write(decode())