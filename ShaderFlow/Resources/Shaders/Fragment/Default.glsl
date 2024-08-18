// A basic cool shader that draws a grid and a ring
// Help: I can't code cool shaders :(

// A Checkerboard grid with `grid` blocks vertically
vec3 grid_layer(vec2 uv, float grid) {

    // Get the grid block color
    if (mod(floor(uv.x * grid/2) + floor(uv.y * grid/2), 2.0) > 0.5) {
        return vec3(0.22);
    } else {
        return vec3(0.2);
    }
}

// A Varying-hue ring that spins
vec4 ring_layer(vec2 uv) {

    // Angle varying in time
    float angle = atan2(uv.y, uv.x) + iTime;

    // Fill the whole Hue range
    vec4 color = hsv2rgb(vec4(angle, 1.0, 1, 1));

    // Ring parameters
    float d = length(uv);
    float r = 0.5;

    // Outside the ring
    if (d > r) {
        color = color * pow(r/d, 15.0);
    } else {
        color = color * pow(d/r, 15.0);
        color.rgb += vec3(0.3);
        color.a = 0.2;

        // Draw a "Simon Says" axis
        if (uv.x < 0) {color.r += 0.3;}
        if (uv.y < 0) {color.g += 0.3;}
        if (uv.x > 0 && uv.y > 0) {
            color.b += 0.3;
        }

        // Cool transparency
        color.a = pow(length(uv/r), 2);
    }

    return color;
}

// ------------------------------------------------------------------------------------------------|

void main() {
    iCameraInit();
    vec2 uv = iCamera.gluv;

    if (iCamera.out_of_bounds) {
        float theta = angle(iCamera.UP, iCamera.ray);
        fragColor.rgb = mix(vec3(0, 0, 0.129), vec3(0.1), pow(abs(theta)/PI, 2.0));
        fragColor.a = 1.0;
        return;
    }

    fragColor.rgb = grid_layer(uv, 8);
    fragColor = alpha_composite(fragColor, ring_layer(uv));
    fragColor.a = 1.0;
}
