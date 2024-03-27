void main() {
    vec3 col = 0.5 + 0.5*cos(iTime + stuv.xyx + vec3(0, 2, 4));
    fragColor = vec4(col, 1.0);
}