/*
In ShaderFlow, the main function is as simple as it can get!

void main() {
    fragColor = vec4(0.2);
}

// Coordinates

All the coordinates are already converted for you:

- astuv: Absolute 'ShaderToy' uv, from (0, 0) to (1, 1)
- agluv: Absolute 'OpenGL' uv, from (-1, -1) to (1, 1)

- stuv: Aspect-ratio corrected astuv
- sgluv: Aspect-ratio corrected agluv

The Top of the screen is always 1, the bottom is 0 or 1 (stuv/gluv)

Or use the iCamera.gluv, iCamera.stuv for a Z=1 plane-projected 2D uv :)

The basis are (Y up), (Z forward), (X right), so (Left-Handed Y up)

- All the Camera Math is already done for 2D, 3D, VR and 360°
  - Just use iCamera.origin and iCamera.target for Ray Marching
  - It works on any "UP" vector in Spherical mode. Quaternion math for the win!
  - Native field of view, dolly zoom parameters

// Quality of Life

With the raw OpenGL bindings provided by ModernGL, the shader compilation
process is much smarter. It simply fixes a lot of your pain and frustration
on ShaderToy, and adds a lot of premium features:

- Inter-operability between types like float and int:
  - No more `cannot convert from 'const int' to 'highp float'` and similar!
- Smooth animations everywhere with a Dynamics system
- Native Fractional Super Sampling Anti Aliasing for first class quality
- Live-reloadable shaders on Path mode, just save the .{frag,glsl,vertex} shader
- Fastest rendering times you'll ever see. Many years of trickery and optimizations

// Expansible

There's no amount and limit of textures channels you can use, defined
on the Scene's Python file. For audio reactiveness, the Spectrogram
math is already there, converting to a log2(y) scale for you.

- Waveforms are already chunked and reduced at your parameters will
- Video as textures are also available, 4k60 fps fluent playback
- Low memory usage, progressively reads the Audio File channels or Real Time mode
- Piano Roll as a texture support. Check out Pianola project for a full example!

// Buffers and Layers

Simply set `texture.layers = L` and `texture.temporal = T` to
create a matrix of LxT 'rolling' textures

Access them by the name of iNameTxL, iName0x* is the current frame and its layers,
iName1x2 is the last frame's layer 2, and so on. Layers starts at 0 and ends in T
*/

void main() {
    GetCamera(iCamera);
    vec3 col = 0.5 + 0.5*cos(iTime + stuv.xyx + vec3(0, 2, 4));
    fragColor = vec4(col, 1.0);
}
