uniform bool iFlip;

void main() {
    vec2 uv = iFlip ? vec2(astuv.x, 1-astuv.y) : (astuv);
    fragColor = texture(iScreen, uv);
    fragColor.a = 1.0;
}