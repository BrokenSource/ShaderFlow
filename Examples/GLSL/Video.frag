void main() {
    iCameraInit();
    vec2 uv = iCamera.astuv;
    fragColor = stexture(iVideo, iCamera.stuv);
    fragColor.a = 1;
}