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

// Channel colors definitions for keys and notes
vec3 getChannelColor(int channel) {
    if (channel == 0) return vec3(0, 1, 0);
    if (channel == 1) return vec3(1, 0, 0);
    if (channel == 2) return vec3(0, 0, 1);
    if (channel == 3) return vec3(1, 1, 0);
    if (channel == 4) return vec3(1, 0, 1);
    if (channel == 5) return vec3(0, 1, 1);
    if (channel == 6) return vec3(1, 1, 1);
    return vec3(0.5);
}

// Get color of a piano key by index
vec3 getKeyColor(int index) {
    if (isWhiteKey(index)) {
        return whiteColor;
    } else {
        return blackColor;
    }
}

// Divisors shenanigans
struct Segment {
    int   A;
    float Ax;
    int   B;
    float Bx;
};

// X: (0 - 1), A: 1-oo, B: 1-oo
Segment makeSegment(float x, int a, int b, int offset) {
    Segment S;
    S.A  = offset + int(a*x);
    S.Ax = fract(a*x);
    S.B  = offset + int(b*x)*2;
    S.Bx = fract(b*x);
    return S;
}

void main() {
    fragColor = vec4(vec3(0.2), 1);
    vec2 uv   = iCamera.astuv;

    // Calculate indices and coordinates
    float k      = abs(mix(iPianoDynamicMin, iPianoDynamicMax, uv.x));
    float nkeys  = abs(iPianoDynamicMax - iPianoDynamicMin);
    float octave = k/12;
    Segment segment;

    /* Ugly calculate segments */ {
        float divisor  = (3.0/7.0);
        bool  first    = fract(octave) < divisor;
        int   offset   = 12*int(octave) + (first?0:5);
        float segmentX = first ? (fract(octave)/divisor) : (fract(octave)-divisor)/(1.0-divisor);
        segment = makeSegment(segmentX, (first?5:7), (first?3:4), offset);
    }

    // Get properties
    int   rollIndex   = segment.A;
    int   keyIndex    = segment.B;
    float rollX       = segment.Ax;
    float whiteX      = segment.Bx;
    float blackHeight = iPianoHeight*(1 - iPianoBlackRatio);
    int   index       = rollIndex;
    vec2  keyStuv;

    // Inside the piano keys and black key
    if (uv.y < iPianoHeight) {
        if (isWhiteKey(rollIndex) || (uv.y < blackHeight)) {
            keyStuv = vec2(whiteX, uv.y/iPianoHeight);
            index   = keyIndex;
        } else {
            keyStuv = vec2(rollX, (uv.y - blackHeight)/(iPianoHeight - blackHeight));
            index   = rollIndex;
        }
    }

    // Get note propertikes
    bool black        = isBlackKey(index);
    bool white        = isWhiteKey(index);
    int  channel      = int(texelFetch(iPianoChan, ivec2(index, 0), 0).r);
    vec3 channelColor = getChannelColor(channel);
    vec3 keyColor     = getKeyColor(index);

    // Inside the piano keys
    if (uv.y < iPianoHeight) {
        vec2  keyGluv = stuv2gluv(keyStuv);
        float press   = abs(texelFetch(iPianoKeys, ivec2(index, 0), 0).r)/128;

        float dark        = black ? 0.6 : 0.8;
        float perspective = 0.11;
        float down        = mix(perspective, 0, press);

        // // Apply coloring
        fragColor.rgb = mix(keyColor, channelColor, pow(press, 0.5));

        if (keyStuv.y < down + iPianoHeight*0.05) {
            // fragColor.rgb *= dark - press*dark;
            fragColor.rgb *= mix(dark, 0.5*dark, press);
        }

        fragColor.rgb *= 0.7 + 0.3*pow(1 - abs(keyGluv.x), 0.1); // Separation
        fragColor     *= mix(1 - 0.05, 1, noise21(uv));

        // Piano and roll separator
        if (uv.y > iPianoHeight*0.98) {
            fragColor.rgb = blackColor;
        } else {
            // Fade to black
            fragColor.rgb *= pow(1 - 0.7*press*(uv.y/iPianoHeight), 1.4);
        }

    // Inside the 'Roll'
    } else {

        // "Roll" coordinate
        vec2  roll     = vec2(uv.x, uv.y - iPianoHeight);
        vec3  keycolor = getKeyColor(index);
        vec3  color    = getChannelColor(channel);
        vec4  note;
        float velocity;
        float press;

        // Search for playing notes: (Start, End, Channel, Velocity)
        for (int i=0; i<iPianoLimit; i++) {
            note     = texelFetch(iPianoRoll, ivec2(index, i), 0);
            velocity = int(note.w);
            if (velocity < 1) break;
            color    = getChannelColor(int(note.z));

            // X: 1/nkeys for this index, so fract of the multiple of
            // Y: Starts at 0 in (roll.y = note.x), ends at 1 in (roll.y = note.y)
            vec2 nastuv = vec2(fract(uv.x*nkeys), (roll.y-note.x)/(note.y-note.x));
            vec2 nagluv = stuv2gluv(nastuv);

            // Inside the note's coordinate
            float n = 20;

            // if (pow(abs(nagluv.x), n) + pow(abs(nagluv.y), n) < 0.9) {
            if (abs(nagluv.y) < 1 && abs(nagluv.x) < 1) {
                fragColor.rgb = color;
                // fragColor.rg += vec2(uv);
                // fragColor.rgb = texture(background, astuv).rgb;
                if (black) {fragColor.rgb *= 0.7;}
            }
        }
    }

    // // Post Effects

    // Vignette
    vec2 vig = astuv * (1 - astuv.yx);
    fragColor.rgb *= pow(vig.x*vig.y * 10, 0.05);
    fragColor.a = 1;

    // Progress bar
    if (uv.y > 0.99 && uv.x < iTau) {
        fragColor.rgb *= 0.8 - 0.2 * smoothstep(0, 1, uv.x);
    }

    // Fade in/out
    float fade = 3;
    fragColor.rgb *= mix(0.5, 1, smoothstep(0, fade, iTime));
    if (iRendering) {
        fragColor.rgb *= mix(1, 0, smoothstep(iTimeEnd - fade, iTimeEnd, iTime));
    }

    return;
}