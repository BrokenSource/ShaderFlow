/*
// (c) MIT, Tremeschin
*/

void main() {
    vec2 uv = iCamera.stuv;

    if (iLayer == 0) {
        fragColor = stexture(background, uv);
    } else if (iLayer == 1) {
        // Average of the last iTemporal layers
        vec4 color = vec4(0);
        for (int i=0; i<iScreenTemporal; i++) {
            float factor = smoothstep(1.0, 0.0, float(i)/iScreenTemporal);
            color += iScreenTexture(i, 0, astuv) * factor;
        }
        fragColor = 2 * color/iScreenTemporal;
    }
    fragColor.a = 1;
}
