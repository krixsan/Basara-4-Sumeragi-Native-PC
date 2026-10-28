#version 450
#extension GL_ARB_separate_shader_objects : enable

layout(set = 0, binding = 0) uniform sampler2D tex;
layout(push_constant) uniform PushConstants {
    vec4 u_texelSize; // xy: 1/width, 1/height; zw: width, height
    vec4 u_settings;  // x: quality_subpix, y: quality_edge_threshold, z: quality_edge_threshold_min
} pc;

layout(location = 0) out vec4 fragColor;

float luma(vec4 c) {
    return dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
}

void main() {
    vec2 uv = gl_FragCoord.xy * pc.u_texelSize.xy;
    vec4 color = texture(tex, uv);
    
    float centerLuma = luma(color);
    
    // Sample neighbors
    float lumaUp = luma(texture(tex, uv + vec2(0.0, pc.u_texelSize.y)));
    float lumaDown = luma(texture(tex, uv - vec2(0.0, pc.u_texelSize.y)));
    float lumaLeft = luma(texture(tex, uv - vec2(pc.u_texelSize.x, 0.0)));
    float lumaRight = luma(texture(tex, uv + vec2(pc.u_texelSize.x, 0.0)));
    
    float lumaMin = min(centerLuma, min(min(lumaUp, lumaDown), min(lumaLeft, lumaRight)));
    float lumaMax = max(centerLuma, max(max(lumaUp, lumaDown), max(lumaLeft, lumaRight)));
    float range = lumaMax - lumaMin;
    
    // Early exit: not an edge
    float threshold = max(pc.u_settings.z, lumaMax * pc.u_settings.y);
    if (range < threshold) {
        fragColor = color;
        return;
    }
    
    // Sample diagonals
    float lumaUpLeft = luma(texture(tex, uv + vec2(-pc.u_texelSize.x, pc.u_texelSize.y)));
    float lumaUpRight = luma(texture(tex, uv + vec2(pc.u_texelSize.x, pc.u_texelSize.y)));
    float lumaDownLeft = luma(texture(tex, uv + vec2(-pc.u_texelSize.x, -pc.u_texelSize.y)));
    float lumaDownRight = luma(texture(tex, uv + vec2(pc.u_texelSize.x, -pc.u_texelSize.y)));
    
    // Edge detection: horizontal vs vertical
    float edgeVertical = abs((lumaUpLeft + lumaUp + lumaUpRight) - (lumaDownLeft + lumaDown + lumaDownRight));
    float edgeHorizontal = abs((lumaUpLeft + lumaLeft + lumaDownLeft) - (lumaUpRight + lumaRight + lumaDownRight));
    
    bool isHorizontal = edgeHorizontal >= edgeVertical;
    
    // Step along edge
    float luma1 = isHorizontal ? lumaDown : lumaLeft;
    float luma2 = isHorizontal ? lumaUp : lumaRight;
    float gradient1 = luma1 - centerLuma;
    float gradient2 = luma2 - centerLuma;
    bool steepestIsPositive = abs(gradient1) >= abs(gradient2);
    
    float stepLength = isHorizontal ? pc.u_texelSize.y : pc.u_texelSize.x;
    
    // Offset calculation
    float offset = 0.0;
    if (steepestIsPositive) {
        offset = stepLength * 0.5;
    } else {
        offset = -stepLength * 0.5;
    }
    
    // Sample at offset
    vec2 uvOffset = isHorizontal ? vec2(0.0, offset) : vec2(offset, 0.0);
    vec4 colorOffset = texture(tex, uv + uvOffset);
    
    // Blend with simple weighting
    float weight = clamp(0.5 + (luma1 - centerLuma) * 0.5, 0.0, 1.0);
    fragColor = mix(color, colorOffset, weight * pc.u_settings.x);
}
