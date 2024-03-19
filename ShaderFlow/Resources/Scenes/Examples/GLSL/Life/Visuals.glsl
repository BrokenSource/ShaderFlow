/*
// (c) MIT, Tremeschin
Conway's Game of Life Visuals
*/

#define COLOR1 vec3(0.01060815, 0.01808215, 0.10018654)
#define COLOR2 vec3(0.38092887, 0.12061482, 0.32506528)
#define COLOR3 vec3(0.79650140, 0.10506637, 0.31063031)
#define COLOR4 vec3(0.95922872, 0.53307513, 0.37488950)

void main() {
    vec2 uv = iCamera.stuv;

    // Rratio of the life temporal integration of f(t) = (1 - t)^k
    // Higher values prefer latest states, lower values smooths all
    float exponent = 1.3;
    float area = 1/(exponent + 1);

    // Integrate life
    float life = 0;
    life += draw_image(iLife0x0, uv).r;
    life += draw_image(iLife1x0, uv).r * pow(0.8, exponent);
    life += draw_image(iLife2x0, uv).r * pow(0.6, exponent);
    life += draw_image(iLife3x0, uv).r * pow(0.4, exponent);
    life += draw_image(iLife4x0, uv).r * pow(0.2, exponent);
    life /= (5*area);

    // Colorize life
    fragColor.rgb = palette(life, COLOR1, COLOR2, COLOR3, COLOR4);
    fragColor.a = 1;
}
