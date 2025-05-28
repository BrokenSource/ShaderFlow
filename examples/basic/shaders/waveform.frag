/*
// (c) MIT, Tremeschin
*/

void main() {
    GetCamera(iCamera);
    vec2 wave = texture(iWaveform, vec2(astuv.x, 0)).rg;
    fragColor = vec4(vec3(0.2), 1);

    if (abs(gluv.y) < wave.x) {
        fragColor.r = 1;
    }
    if (abs(gluv.y) < wave.y) {
        fragColor.g = 1;
    }
    if (abs(gluv.y) < (wave.x + wave.y)/2) {
        fragColor.b = 1;
    }
}