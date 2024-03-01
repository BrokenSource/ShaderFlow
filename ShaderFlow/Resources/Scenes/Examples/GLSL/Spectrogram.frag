/*
// (c) MIT, Tremeschin
*/

void main() {
    vec2 uv = gluv2stuv(agluv * 0.99);
    uv.x += iSpectrogramOffset;
    vec2 spec = pow(texture(iSpectrogram, uv).xy/150, vec2(0.5));
    fragColor.rgb = vec3(0.2) + vec3(spec.x, pow(spec.x + spec.y, 2), spec.y);
    fragColor.a = 1;
}
