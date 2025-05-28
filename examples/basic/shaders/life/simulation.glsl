/*
// (c) MIT, Tremeschin
Conway's Game of Life Simulation
*/

// Live cells with two or three neighbours survive
const int alive[9] = int[9](
    0, 0, 1,
    1, 0, 0,
    0, 0, 0
);

// Dead cell swith three neighbours becomes alive
const int dead[9] = int[9](
    0, 0, 0,
    1, 0, 0,
    0, 0, 0
);

void main() {
    int near = 0;
    int current;

    // Make the animation slower
    if ((iFrame % iLifePeriod) != 0) {
        fragColor.r = texture(iLife1x0, astuv).r;
        fragColor.a = 1;
        return;
    }

    ivec2 pixel = ivec2(astuv*iLifeSize);

    // Integrate the rules kernel
    for (int x=-1; x<=1; x++) {
        for (int y=-1; y<=1; y++) {
            ivec2 point = pixel + ivec2(x, y);
            int cell = texelFetch(iLife1x0, point, 0).r > 0.5 ? 1:0;
            if (x==0 && y==0) {
                current = cell;
            } else {
                near += cell;
            }
        }
    }

    // Apply the rules
    fragColor.r = (current==1)?alive[near]:dead[near];
    fragColor.a = 1;
}