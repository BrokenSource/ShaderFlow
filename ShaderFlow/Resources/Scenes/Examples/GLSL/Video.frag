void main() {
    vec2 uv = iCamera.astuv;

    // Plain video, no shenanigans :D
    if (true) {
        fragColor = draw_image(iVideo, iCamera.stuv);

    // Draw a sweep of (current >> old) frames
    } else if (false) {
        int n = int(mix(0, iVideoPast, uv.x));
        fragColor = draw_image(iVideoGet(n, 0), iCamera.stuv);

    // Poor's man motion blur
    } else if (false) {
        vec4 color = vec4(0.0);
        for (int i = 0; i < iVideoPast; i++) {
            color += draw_image(iVideoGet(i, 0), iCamera.stuv);
        }
        fragColor = color / float(iVideoPast);
    }

    fragColor.a = 1;
}