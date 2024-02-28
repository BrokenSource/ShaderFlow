#define whiteColor vec3(0.9)
#define blackColor vec3(0.2)

// Each octave contains 12 keys, black keys have a constant offset
bool isBlackKey(int index) {
    int key = index % 12;
    return key == 1 || key == 3 || key == 6 || key == 8 || key == 10;
}

// Can only be black or white
bool isWhiteKey(int index) {
    return !isBlackKey(index);
}

// Get color of a piano key by index
vec3 keyColor(int index) {
    if (isWhiteKey(index)) {
        return whiteColor;
    } else {
        return blackColor;
    }
}

// Channel colors definitions for keys and notes
vec3 channel_color(int channel) {
    if (channel == 0) return vec3(0, 1, 0);
    if (channel == 1) return vec3(1, 0, 0);
    if (channel == 2) return vec3(0, 0, 1);
    if (channel == 3) return vec3(1, 1, 0);
    if (channel == 4) return vec3(1, 0, 1);
    if (channel == 5) return vec3(0, 1, 1);
    if (channel == 6) return vec3(1, 1, 1);
    return vec3(0.5);
}

void main() {
    fragColor.rgb = vec3(0.2);
    vec2 uv = iCamera.astuv;

    // // Background

    vec2 background_uv = zoom(iCamera.gluv, 0.93 - 0.04*iAudioVolume, vec2(0));
    fragColor.rgb = draw_image(background, g2s(background_uv)).rgb*0.8;

    // // "Piano"

    // Get the piano key index of this vertical strip
    int   index       = int(mix(iPianoMin, iPianoMax+1, uv.x));
    int   nkeys       = iPianoMax - iPianoMin + 1;
    bool  black       = isBlackKey(index);
    bool  white       = isWhiteKey(index);
    int   channel     = int(texelFetch(iPianoChan, ivec2(index, 0), 0).r);
    float blackHeight = iPianoHeight*0.4;

    // "Roll" coordinate
    vec2  roll     = vec2(uv.x, uv.y-iPianoHeight);
    vec3  keycolor = keyColor(index);
    vec3  color    = channel_color(channel);
    vec4  note;
    float velocity;
    float press;

    // Search for playing notes: (Start, End, Channel, Velocity)
    for (int i=0; i<iPianoLimit; i++) {
        note     = texelFetch(iPianoRoll, ivec2(index, i), 0);
        velocity = int(note.w);
        if (velocity < 1) break;
        color    = channel_color(int(note.z));

        // X: 1/nkeys for this index, so fract of the multiple of
        // Y: Starts at 0 in (roll.y = note.x), ends at 1 in (roll.y = note.y)
        vec2 nastuv = vec2(
            fract(uv.x*nkeys),
            (roll.y - note.x) / (note.y - note.x)
        );
        vec2 nagluv = stuv2gluv(nastuv);

        // Inside the note's coordinate
        float n = 20;
        if (pow(abs(nagluv.x), n) + pow(abs(nagluv.y), n) < 0.9) {
        // if (abs(nagluv.y) < 1 && abs(nagluv.x) < 1) {
            fragColor.rgb = color;
            // fragColor.rg += vec2(uv);
            if (black) {fragColor.rgb *= 0.5;}
        }

    }

    // // "Roll"

    // Fade to black when near the bottom piano
    fragColor.rgb *= 1 - 0.7 * smoothstep(0.1, 0, roll.y);

    // Inside the Piano keys
    if (uv.y < iPianoHeight) {
        press = abs(texelFetch(iPianoKeys, ivec2(index, 0), 0).r)/128;
        float dark = 0.8;
        float perspective = 0.11;

        if (white || uv.y < blackHeight) {
            float down = perspective;

            if (white) {
                down = mix(perspective, 0, press);
                fragColor.rgb = mix(whiteColor, color, pow(press, 0.5));
            } else {
                fragColor.rgb = whiteColor;
            }

            if (uv.y < iPianoHeight*down) {fragColor.rgb *= dark - 0.5*down;} // Perspective
            fragColor.rgb *= 1 - 0.7*press*(uv.y/iPianoHeight); // Fade to black
        } else {
            fragColor.rgb = mix(blackColor, color, pow(press, 0.5));

            if (uv.y < blackHeight + iPianoHeight*mix(perspective, 0, press)) {
                fragColor.rgb *= pow(dark, 3);} // Perspective
        }

        // Add some noise / dithering
        fragColor *= mix(1 - 0.05, 1, noise21(uv));

        // Separation between notes. Todo: Wrong below black keys
        float note_x = (fract(uv.x*nkeys)*2) - 1;
        fragColor.rgb *= 0.7 + 0.3*pow(1 - abs(note_x), 0.1);

        // Piano and roll separator
        if (uv.y > iPianoHeight*0.99) {
            fragColor.rgb = blackColor;
        }
    }

    // // Post Effects

    // Vignette
    vec2 vig = astuv * (1 - astuv.yx);
    fragColor.rgb *= pow(vig.x*vig.y * 10, 0.05);
    fragColor.a = 1;

    // Progress bar
    if (uv.y > 0.98 && uv.x < iTau) {
        fragColor.rgb *= 1.8;
    }
}