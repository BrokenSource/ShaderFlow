---
title: ShaderFlow/ShaderScene
icon: material/application-brackets-outline
---

!!! warning "🚧 Work in Progress 🚧"

## Resolution


### Aspect ratio

<b><span class="the">T</span>he aspect</b> ratio of a resolution is the ratio between its width and height. Two interpretations are: _"How many times wider is the resolution than it is tall?"_, and a numeric one: _"If the top value is 1 relative to the center, what is the $x$ value on each side?"_

The value of `self.aspect_ratio` will always be `self.width/self.height` at any given time, and an internal attribute `self._aspect_ratio` controls how resizes are calculated.

### Resizes

<b><span class="the">T</span>he resolution</b> a Scene will render in realtime or export to a video file is calculated inside the `main` method. The final value weakly depends on the state prior calling it, and strongly on a few incoming arguments, namely `width`, `height`, `ratio` and `scale`.

The **internal** starting value of a Scene's resolution is 1920x1080 (Full HD), with no enforced aspect ratio (dynamic), and a scale of 1. This is the default output resolution if no such related arguments are passed, and no `self.*` attributes were changed anywhere.

1. The value of `self._aspect_ratio` is None

This is the simplest case. Any value passed on either `width` or `height` will override the respective `self.*` attribute, not affecting the other. The final resolution is post-multiplied by `self.scale`. For example, rendering with `width=1280, height=None` will give a `1280x1080` video, and rendering with `scale=2` gives `3840x2160`.

2. The value of `self._aspect_ratio` is a float

This will enforce the aspect ratio of the resolution.

If only one of `width` or `height` are passed, ShaderFlow will calculate the other based on the aspect ratio, and force the one sent. For example, `ratio=1` and `width=1280` will give a `1280x1280` video, and `ratio=16/9` and `height=1440` will give a `2560x1440` video.

If both `width` and `height` are passed, ShaderFlow will take preference to `width` over `height` in the calculations. For example, `ratio=16/9` and `width=1280, height=1280` will give a `1280x720` video.

The value is post-multiplied by `self.scale` as always.

