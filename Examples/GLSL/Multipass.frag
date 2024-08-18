/*
// (c) MIT, Tremeschin
*/

/** Walk in circles around the pixel and integrate samples, divide by area
 * • Radius: How far to walk to sample the blur
 * • Directions: Number of "rays" to cast
 * • Steps: Number of samples per ray until the radius is reached
 */
vec4 blur(sampler2D image, vec2 stuv, float radius, int directions, int steps) {
    vec4 color = vec4(0);
    float weights = 0.0;

    for (float direction=0; direction<TAU; direction+=TAU/directions) {
        for (float walk=1.0/steps; walk<1.0; walk+=1.0/steps) {
            vec2 offset = vec2(cos(direction), sin(direction)) * radius * walk / 2000;
            vec4 sample = texture(image, stuv + offset);
            float weight = 1.0 - distance(offset, vec2(0)) / float(radius);
            color += sample * weight;
            weights += weight;
        }
    }

    return color / weights;
}

void main() {
    iCameraInit();

    if (iLayer == 0) {
        fragColor = stexture(background, stuv);

    } else if (iLayer == 1) {
        fragColor = texture(iScreen0x0, astuv);

        // Invert red on the left, blur the right
        if (gluv.x < 0) {
            fragColor.r = 1 - fragColor.r;
        } else {
            fragColor = blur(iScreen0x0, astuv, 5, 8, 8);
        }
    }

    fragColor.a = 1;
}
