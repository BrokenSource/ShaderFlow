/*
// (c) MIT, Tremeschin
*/

void main() {
    if (iLayer == 0) {
        fragColor = draw_image(background, stuv);

    } else if (iLayer == 1) {
        fragColor = texture(iScreen1, astuv);
    }

    fragColor.a = 1;
}
