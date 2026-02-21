# Spec: Materials & Visual Effects

## Goal
Add realistic materials (refraction, emission) and post-processing (bloom) for the ethereal visual style.

## Depends On
- `04-faux-physics.md`

## Acceptance Criteria

1. Material system with properties:
   - Base color (HDR, allows glow)
   - Roughness (0.0 - 1.0)
   - Metallic (0.0 - 1.0)
   - Index of Refraction (IOR: 1.0 - 3.0, default 1.33)
   - Emission strength (0.0 - 10.0)

2. Refraction implementation in fragment shader:
   - Ray march to surface
   - Calculate normal
   - Refract ray through volume
   - March again to exit point
   - Blend with environment

3. Emission/glow:
   - Per-material emission color
   - Intensity linked to physics velocity
   - Smooth interpolation during motion

4. Post-processing:
   - Bloom via Unity's volume framework
   - Threshold: 1.0, Intensity: 0.5
   - Tone mapping: ACES

5. Visual presets:
   - Glass (IOR 1.5, low roughness, emission 0)
   - Jelly (IOR 1.33, medium roughness, pastel emission)
   - Neon (IOR 1.0, zero roughness, high emission)

6. Scene demonstrating all materials

## Out of Scope
- Subsurface scattering (future)
- Volumetric fog (future)
- Complex environment maps
