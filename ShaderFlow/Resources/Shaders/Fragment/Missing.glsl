// Missing texture shader. Definitely not inspired in Source Shader

void main() {

    // Walk through the texture
    vec2 uv = stuv + vec2(iTime) / 64.0;

    // Vertical grid size
    float size = 8.0;

    // Create missing texture
    for (int x = -5; x < 5; x++) {
        for (int y = -5; y < 5; y++) {
            vec2 block = floor(size * uv);
            if (mod(block.x + block.y, 2.0) == 0.0) {
                fragColor.rgb += vec3(1.0, 0.0, 1.0) / 25.0;
            }
        }
    }

    // Lots of transparency to see other elements
    fragColor.a = 0.2;
}