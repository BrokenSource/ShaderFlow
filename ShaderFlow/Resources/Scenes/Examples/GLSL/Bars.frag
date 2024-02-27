void main() {
    vec2 intensity = sqrt(texture(iSpectrogram, astuv.yx).xy / 100);

    if (astuv.y < intensity.x) {
        fragColor.rgb += vec3(1.0, 0.0, 0.0);
    }
    if (astuv.y < intensity.y) {
        fragColor.rgb += vec3(0.0, 1.0, 0.0);
    }
    if (astuv.y < (intensity.y + intensity.x)/2.0) {
        fragColor.rgb += vec3(0.0, 0.0, 1.0);
    }

    fragColor.rgb += vec3(0.0, 0.0, 0.4*(intensity.x + intensity.y)*(1.0 - astuv.y));
    fragColor.a = 1;
}