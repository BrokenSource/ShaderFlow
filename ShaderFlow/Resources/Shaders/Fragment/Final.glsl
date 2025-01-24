uniform int iSubsample;

void main() {

    // Center sample is trivial
    if (iSubsample == 1) {
        fragColor = texture(iScreen, astuv);
        fragColor.a = 1.0;
        return;
    }

    // Integrate a color over a grid of samples
    vec3 accumulator = vec3(0.0);
    int kernel = iSubsample;

    // Divided by aspect because
    vec2 pixel_size = vec2(
        (1.0/iResolution.x)/iAspectRatio,
        (1.0/iResolution.y)
    );

    // Calculate starting offset to center the sampling grid
    vec2 corner = astuv  - (pixel_size/2);
    vec2 origin = corner + (pixel_size/kernel)/2;

    for (int x=0; x<kernel; x++) {
        for (int y=0; y<kernel; y++) {
            vec2 offset = (pixel_size / kernel) * vec2(x, y);
            accumulator += texture(iScreen, origin + offset).rgb;
        }
    }

    // Normalize the final color
    fragColor.rgb = (accumulator / float(kernel*kernel));
    fragColor.a = 1.0;
}
