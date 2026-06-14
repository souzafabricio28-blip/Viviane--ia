#version 330 core

uniform float u_time;
uniform int u_is_line;

in vec3 v_color;
out vec4 fragColor;

void main() {
    float pulse = (sin(u_time * 3.0) + 1.0) / 2.0;

    vec3 colorVerde = vec3(0.0, 1.0, 0.5);
    vec3 colorMagenta = vec3(1.0, 0.0, 0.5);

    if (u_is_line == 1) {
        // Neural network connections: pulse between teal-green and magenta
        vec3 pulseColor = mix(colorVerde, colorMagenta, pulse);
        fragColor = vec4(pulseColor * v_color.r, 0.8);
    } else {
        // Nodes: Earth terrain with subtle pulse glow on front faces
        vec3 glow = mix(vec3(0.0, 0.15, 0.08), vec3(0.15, 0.0, 0.08), pulse);
        fragColor = vec4(v_color + glow, 0.9);
    }
}
