/*
// (c) MIT, Tremeschin
// Hours wasted: 6
*/

#define ADVANCED_CORRECTION false

void main() {
    iCameraInit();
    float angle;
    float aspect;

    // Take into account rotation and image contents
    // Fixme: Vertical stretching is slightly wrong
    if (ADVANCED_CORRECTION) {
        // aspect = texture(iBounceAspectRatio, vec2(angle/TAU, 0.5)).r;
        // angle = iTime/2;
    } else {
        aspect = logoSize.y / logoSize.x;
        angle = iTime/2;
    }

    // Calculate the coordinate, a lot going on I wished to explain
    vec2 correction = (1 - iLogoSize*vec2(aspect/iAspectRatio, 1));
    vec2 uv = (gluv - iBouncePosition*correction) / iLogoSize;
    uv *= rotate2d(angle);

    // // Grid - Not part of the tech demo

    // Background
    int grid_spacing = 100;
    int grid_thick = 2;
    float size1 = 180.0;

    // Background color
    fragColor = vec4(vec3(0.3), 1);

    // Grid marks when spacing fract (mod) pixel distance is less than value
    bool _x = mod(glxy.x, grid_spacing) > (grid_spacing - grid_thick);
    bool _y = mod(glxy.y, grid_spacing) > (grid_spacing - grid_thick);
    if (_x || _y) {
    	fragColor = vec4(vec3(0.2), 1);
    }

    // // Draw the bouncing logo

    if (!agluv_oob(uv)) {
        fragColor = alpha_composite(fragColor, gtexture(logo, uv));
    }
}

