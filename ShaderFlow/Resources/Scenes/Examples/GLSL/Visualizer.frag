/*
// (c) MIT, Tremeschin, I Hate This Code
*/

// Not proud of this shader :v
void main() {
    vec2 uv = iCamera.gluv;
    vec3 space = vec3(1, 11, 26) / 255;

    if (iCamera.out_of_bounds) {
        fragColor.rgb = space;
        return;
    }

    // Draw background
    vec2 background_uv = zoom(gluv2stuv(uv), 0.95 + 0.01*sin(iTime) - 0.02*iAudioVolume - 0.03, vec2(0.5));
    background_uv += 0.005 * vec2(cos(iTime*3.25135), sin(iTime*1.153469));
    fragColor = stexture(background, background_uv);

    /* Blur background on audio volume */ {
        float intensity = 0.01*clamp(pow(iAudioVolume, 2.5), 0, 0.3);
        float quality = 10;
        float directions = 8;
        vec4 color = fragColor;
        for (float angle=0; angle<TAU; angle+=TAU/directions) {
            for (float walk=1.0/quality; walk<=1.001; walk+=1.0/quality) {
                vec2 displacement = vec2(cos(angle), sin(angle)) * walk * intensity;
                color += stexture(background, background_uv + displacement);
            }
        }
        fragColor = color / (quality*directions);
    }

    // Blink on snare/kick
    fragColor *= 1 + 5*iAudioSTD*pow(clamp(length(agluv) - 0.3, 0, 1), 6);

    // Music bars coordinates
    vec2 music_uv = rotate2d(-PI/2) * uv;
    music_uv *= 1 - 0.4 * pow(abs(iAudioVolume), 0.5);
    float radius = 0.17;

    // Get spectrogram bar volumes
    float circle = abs(atan1n(music_uv));
    vec2 freq = sqrt(texture(iSpectrogram, vec2(0, circle)).xy / 1000);
    freq *= 0.05 + 3*smoothstep(0, 2, circle);

    // Music bars
    if (length(music_uv) < radius) {
        vec2 logo_uv = (rotate2d(0.3*sin(3*iAudioVolumeIntegral + iTime/2)) * music_uv / (1.3*radius));
        logo_uv *= 1 - 0.02*pow(abs(iAudioVolume), 0.1);
        fragColor = gtexture(logo, logo_uv * rotate2d(-PI/2));
    } else {
        float bar = (music_uv.y < 0) ? freq.x : freq.y;
        float r = radius + 0.5*bar;

        if (length(music_uv) < r) {
            fragColor.rgb = mix(fragColor.rgb, vec3(1), smoothstep(0, 1, 0.5 + bar));
        } else {
            fragColor.rgb *= pow((length(music_uv) - r) * 0.5, 0.05);
        }
    }

    fragColor.rgb = mix(fragColor.rgb, space, smoothstep(0, 1, length(uv)/20));

    // Vignette
    vec2 vig = astuv * (1 - astuv.yx);
    fragColor.rgb *= pow(vig.x*vig.y * 20, 0.1 + 0.15*iAudioVolume);
    fragColor.a = 1;


    // Waveform on top and bottom
    vec2 wave = 0.2*texture(iWaveform, vec2(astuv.x, 0)).rg;
    if (1 - gluv.y < wave.x) {fragColor *= 0.8;}
    if (1 + gluv.y < wave.y) {fragColor *= 0.8;}
}