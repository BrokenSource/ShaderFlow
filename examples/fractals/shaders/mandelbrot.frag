
// Complex multiplication
vec2 cmul(vec2 a, vec2 b) {
    return vec2(
        a.x * b.x - a.y * b.y,
        a.x * b.y + a.y * b.x
    );
}

void main() {
    GetCamera(iCamera);

    if (iCamera.out_of_bounds) {
        fragColor = vec4(palette_magma(0), 1);
    } else {
        vec2 z = iCamera.gluv - vec2(0.5, 0.0);
        vec2 c = z;

        int quality = int(1000.0 * iQuality);
        int iter = 0;

        for (; iter<quality; iter++) {
            if (length(z) > 3.0) break;
            z = cmul(z, z) + c;
        }

        // Nice shading pallete
        float t = pow(1 - float(iter) / quality, 20);
        fragColor = vec4(palette_magma(t), 1);
    }
}