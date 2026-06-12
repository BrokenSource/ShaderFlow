---
title: License
icon: material/license
---

!!! warning "Work in progress"

## Code

ShaderFlow is licensed under the AGPLv3, a strong copyleft license to ensure it remains Free and Open Source for all users.

## Liability

### Content

User Generated Content (...)

### Codecs

Certain FFmpeg codecs may be covered by patents in some jurisdictions. Chances are you'll never get into trouble by sharing private or public facing videos, but selling may require attention.

ShaderFlow defaults to the following options and their reasoning:

- **Video**: Uses H.264 (mostly expired patents)[^h264] for performance and compatibility. Other royalty-free options such as AV1 may take its place in the future to move the ecosystem forward.
- **Audio**: Copies the original file into the video for best quality, avoiding a re-encode.

[^h264]: Wikimedia: [Have the patents for H.264 MPEG-4 AVC expired yet?](https://meta.wikimedia.org/wiki/Have_the_patents_for_H.264_MPEG-4_AVC_expired_yet%3F)

Other options are available in the wrappers, note it includes 'non-free' ones for completeness and research purposes. Users must ensure compliance and follow external terms when applicable.

<small><b>Read more:</b> https://ffmpeg.org/legal.html</small>
