/*
// (c) 2024 CC BY-SA 4.0, Tremeschin, part of ShaderFlow project.
*/

// Color Palette
#define COLOR1 vec3(0.01060815, 0.01808215, 0.10018654)
#define COLOR2 vec3(0.38092887, 0.12061482, 0.32506528)
#define COLOR3 vec3(0.79650140, 0.10506637, 0.31063031)
#define COLOR4 vec3(0.95922872, 0.53307513, 0.37488950)

// Others
#define PIANO_SIZE  0.03
#define BORDER_SIZE 0.1
#define BLEED 0.005

// Frequency -> Octave-like
float to_scale(float frequency) {
    return log(frequency)/log(2.0);
}

// Octave-like -> Frequency
float from_scale(float octave) {
    return pow(2.0, octave);
}

// Get the "real" frequency of a given y coordinate
float get_frequency(float y) {
    return from_scale(mix(to_scale(iSpectrogramMin), to_scale(iSpectrogramMax), y));
}

void main() {

    // Get the spectrogram uv coordinate
    vec2 spectrogram_uv = vec2(lerp(PIANO_SIZE, BLEED, 1-PIANO_SIZE, 1-BLEED, astuv.x), astuv.y);
    spectrogram_uv.x += iSpectrogramStill ? 0:iSpectrogramOffset;

    // Calculate the color
    vec2 intensity = pow(texture(iSpectrogram, spectrogram_uv).xy, vec2(0.8))/30;
    vec3 left  = palette(intensity.x, COLOR1, COLOR2, COLOR3, COLOR4);
    vec3 right = palette(intensity.y, COLOR1, COLOR2, COLOR3, COLOR4);
    fragColor  = vec4((left+right)/2, 1);

    // Constants based on the definitions
    float PIANO_STARTS  = (1-(2*PIANO_SIZE));
    float BORDER_STARTS = (1-(2*PIANO_SIZE)*(1-BORDER_SIZE));
    bool  INSIDE_REGION = (abs(agluv.x) > PIANO_STARTS);
    bool  INSIDE_PIANO  = (abs(agluv.x) > BORDER_STARTS);

    // Same idea as on the Python spectrogram code
    float frequency = get_frequency(astuv.y);
    float key       = (12*log2(frequency/440.0) + 69) - 0.5;
    int   modKey    = int(mod(key, 12.0));
    bool  black     = (modKey==1||modKey==3||modKey==6||modKey==8||modKey==10);

    // Draw the piano keys and key separation
    if (INSIDE_REGION) {
        if (black && abs(agluv.x) > PIANO_STARTS + 0.8*PIANO_SIZE) {
            fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        } else {
            fragColor = vec4(1.0, 1.0, 1.0, 1.0);
        }
        fragColor.rgb *= 0.5 + 0.5*pow(1 - abs(fract(key)*2-1), 0.1);
    }

    // Black border coordinates and color it
    vec2 buv = vec2(lerp(PIANO_STARTS, -1, BORDER_STARTS, 1, abs(agluv.x)), astuv.y);
    fragColor.rgb = (abs(buv.x)>1) ? fragColor.rgb : (abs(buv.x)<0.5?vec3(0.25):vec3(0));

    // Horizontal line that snaps to the piano key where the mouse is
    float mouse_key = (12*log2(get_frequency((iMouse.y+1)/2)/440.0) + 69);

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
