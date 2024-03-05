/*
// (c) 2024 CC BY-SA 4.0, Tremeschin, part of ShaderFlow project.
*/

// Color Palette
#define COLOR1 vec3(0.01060815, 0.01808215, 0.10018654)
#define COLOR2 vec3(0.38092887, 0.12061482, 0.32506528)
#define COLOR3 vec3(0.79650140, 0.10506637, 0.31063031)
#define COLOR4 vec3(0.95922872, 0.53307513, 0.37488950)
#define BLEED 0.005

const float HALF_SEMITONE = pow(2.0, 1.0/24);

// Frequency -> Octave-like
float to_scale(float frequency) {
    return log2(frequency);
}

// Octave-like -> Frequency
float from_scale(float octave) {
    return pow(2.0, octave);
}

// Get the frequency of a given y coordinate relative to min and max frequencies
// Note: Times half a semitone as the key's center is min/max frequency
float get_frequency(float y) {
    return from_scale(mix(
        to_scale(iSpectrogramMin / HALF_SEMITONE),
        to_scale(iSpectrogramMax * HALF_SEMITONE),
        y
    ));
}

void main() {
    vec2 suv = astuv;
    vec2 mouse = iMouse;

    // Vertical spectrogram (-> pitch ->)
    if (iVertical) {
        suv = vec2(1 - suv.y, suv.x);
        mouse = vec2(1 - mouse.y, mouse.x);
    }

    // Get the GLUV we'll use
    vec2 guv = s2g(suv);

    // Get the spectrogram uv coordinate
    vec2 spectrogram_uv = vec2(lerp(iPianoSize, BLEED, 1-iPianoSize, 1-BLEED, suv.x), suv.y);
    spectrogram_uv.x += iSpectrogramStill ? 0:iSpectrogramOffset;

    // Calculate the color
    vec2 intensity = pow(texture(iSpectrogram, spectrogram_uv).xy, vec2(0.8))/30;
    vec3 left  = palette(intensity.x, COLOR1, COLOR2, COLOR3, COLOR4);
    vec3 right = palette(intensity.y, COLOR1, COLOR2, COLOR3, COLOR4);
    fragColor  = vec4((left+right)/2, 1);

    // Constants based on the definitions
    float PIANO_STARTS  = (1-(2*iPianoSize));
    float BORDER_STARTS = (1-(2*iPianoSize)*(1-iBorderRatio));
    bool  INSIDE_REGION = (abs(guv.x) > PIANO_STARTS);
    bool  INSIDE_PIANO  = (abs(guv.x) > BORDER_STARTS);
    bool  RIGHT_SIDE    = (guv.x > 0);
    float TRUE_RATIO    = (RIGHT_SIDE ? iBlackRatio+iBorderRatio : 1-iBlackRatio);
    float BLACK_STARTS  = (PIANO_STARTS + 2*TRUE_RATIO*iPianoSize);
    bool  BLACK_REGION  = (abs(guv.x)<BLACK_STARTS);

    // Invert black and white region if on the other side
    BLACK_REGION = RIGHT_SIDE ? BLACK_REGION : !BLACK_REGION;

    // Same idea as on the Python spectrogram code
    float frequency = get_frequency(suv.y);
    float key       = (12*log2(frequency/440.0) + 69) + 0.5;
    bool  black     = isBlackKey(key);

    // Draw the piano keys and key separation
    if (INSIDE_PIANO) {
        if (black && BLACK_REGION) {
            fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        } else {
            fragColor = vec4(1.0, 1.0, 1.0, 1.0);
        }
        fragColor.rgb *= 0.5 + 0.5*pow(1 - abs(fract(key)*2-1), 0.1);
    }

    // Black border coordinates and color it
    vec2 buv = vec2(lerp(PIANO_STARTS, -1, BORDER_STARTS, 1, abs(guv.x)), suv.y);
    fragColor.rgb = (abs(buv.x)>1) ? fragColor.rgb : (abs(buv.x)<0.5?vec3(0.25):vec3(0));

    // Horizontal line that snaps to the piano key where the mouse is
    float mouse_key = (12*log2(get_frequency((mouse.y+1)/2)/440.0) + 69);

    if (int(mouse_key) == int(key)) {
        if (INSIDE_PIANO) {
            // fragColor.rgb += vec3(0.5, 0, 0);
            if (black) {
                fragColor.rgb += vec3(0.5, 0, 0);
            } else {
                fragColor.rgb = vec3(0.5, 0, 0);
            }
        } else {
            fragColor.rgb *= 0.4;
        }
    }
}
