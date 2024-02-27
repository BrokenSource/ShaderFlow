bool isBlackKey(int index) {
    int key = index % 12;
    return key == 1 || key == 3 || key == 6 || key == 8 || key == 10;
}

bool isWhiteKey(int index) {
    return !isBlackKey(index);
}

#define whiteColor vec3(0.9)
#define blackColor vec3(0.2)

vec3 getColor(int index) {
    if (isWhiteKey(index)) {
        return whiteColor;
    } else {
        return blackColor;
    }
}

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
    vec2 uv = astuv;

    // Get the piano key index of this vertical strip
    int  index   = int(mix(iPianoMin, iPianoMax+1, uv.x));
    int  nkeys   = iPianoMax - iPianoMin;
    bool black   = isBlackKey(index);
    bool white   = isWhiteKey(index);
    int  channel = int(texelFetch(iPianoChan, ivec2(index, 0), 0).r);

    // "Roll" coordinate
    vec2  roll     = vec2(uv.x, mix(-iPianoHeight, 1, uv.y));
    vec3  keycolor = getColor(index);
    vec3  color    = channel_color(channel);
    vec4  note;
    float velocity;
    float press;

    // Search for playing notes (Start, End, Channel, Velocity)
    for (int i=0; i<iPianoLimit; i++) {
        note     = texelFetch(iPianoRoll, ivec2(index, i), 0);
        velocity = int(note.w);
        if (velocity < 1) break;
        channel  = int(note.z);
        color    = channel_color(channel);

        // X: Starts at index/
        vec2 note_uv = vec2(fract(astuv.x*nkeys), (note.y - note.x)/(1 - iPianoHeight));

        if (roll.y > note.x && roll.y < note.y) {
            fragColor.rgb = color;
            break;
        }
    }

    fragColor.rgb *= pow(roll.y, 0.2);

    // Inside the Piano keys
    if (uv.y < iPianoHeight) {
        press = texelFetch(iPianoKeys, ivec2(index, 0), 0).r/128;
        fragColor.rgb = mix(keycolor, color, pow(abs(press), 0.5));

        if (black && uv.y < iPianoHeight*0.4) {
            fragColor.rgb = whiteColor;
        }

        if (uv.y < iPianoHeight*mix(0.13, 0, press)) {
            fragColor.rgb *= 0.6;
        }
    }

    // Vignette
    vec2 vig = astuv * (1 - astuv.yx);
    fragColor.rgb *= pow(vig.x*vig.y * 10, 0.05);
    fragColor.a = 1;
}