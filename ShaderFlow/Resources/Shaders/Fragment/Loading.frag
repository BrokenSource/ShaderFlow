/*
// (c) MIT, Tremeschin
*/

void main() {
    fragColor.rgb = vec3(0);

	// Loading icon options
    float radius = 0.5;
	float width  = 15.0;
	float glow   = 2.0;

    // Fixme: Should this be a uniform
    float pixel = 1.0/min(iResolution.x, iResolution.y);

	// Convert to pixel-space
	width *= pixel;
	glow  *= pixel*2;

	// Calculate Tail Size based on Angle
	float angle = atan(gluv.y, gluv.x);
	float tail  = smoothstep(0.3, 1, fract((1.5*angle/PI) - iTime));

	// Calculate
    width = (width - pixel)*0.5*tail;

    float ring  = abs(length(gluv) - radius) - width;

	// Get the final height of the effect
	float height;
	height += smoothstep(pixel,     0.0, ring) * tail;
	height += smoothstep(glow*tail, 0.0, ring) * tail*0.5;

	// Add loading ring
	fragColor = hsv2rgb(vec4(angle-iTime, height, 1, 1)) * height;

	// Dark theme
	fragColor.rgb += vec3(0.15);
	fragColor.a = 1.0;
}
