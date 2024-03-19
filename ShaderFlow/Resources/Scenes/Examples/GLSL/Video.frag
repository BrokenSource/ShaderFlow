void main() {
    vec2 uv = iCamera.astuv;
    fragColor = draw_image(iVideo, iCamera.stuv);
    fragColor.a = 1;
}