#define LOGO false

// A Checkerboard `grid` blocks vertically
vec3 grid(vec2 uv, float grid) {
    if (mod(floor(uv.x * grid/2) + floor(uv.y * grid/2), 2.0) > 0.5)
        return vec3(0.22);
    return vec3(0.20);
}

void main() {
    GetCamera(iCamera);
    fragColor = vec4(0.0);
    vec2 uv = iCamera.gluv;

    if (iCamera.out_of_bounds) {
        fragColor.rgb = vec3(0.15);
        fragColor.a = 1.0;
    } else {

        // Custom atan2 (0, 2pi)
        float angle = atan2(uv);

        // Add a color bias for full white neon ring
        vec3 color = vec3(0.3) + hsv2rgb(angle + (2*TAU*iTau) - (PI/4), 1, 1);

        // Move the origin away, find fade multiplier
        float circle = (1.333*length(uv) - 1.0);
        float width = 2 * abs(1/(circle*circle)) * 1e-4;

        // Add the grid only inside the circle
        if (circle < 0.0) {
            fragColor.rgb += vec3(0.18);
        } else {
            fragColor.rgb += LOGO ? vec3(0.1) : grid(uv, 8.0);
        }

        // Add the hsv ring to the final color
        fragColor.rgb += (width * color);
        fragColor.a = 1.0;

        // Vignette effect
        vec2 away = astuv * (1.0 - astuv.yx);
        float linear = 50 * (away.x*away.y);
        fragColor.rgb *= clamp(pow(linear, 0.1), 0.0, 1.0);

        // Todo: Letter 'S' in the middle :^)
    }
}


