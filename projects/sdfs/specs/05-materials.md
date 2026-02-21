# Spec: Materials & Visual Effects

## Goal
Add realistic materials (refraction, emission) and post-processing (bloom) for the ethereal visual style.

## Depends On
- `04-faux-physics.md`

## Implementation Notes

### URP vs Custom Raymarching
- **Critical Issue**: Standard URP Lit shaders won't work with raymarching. You must extend the SDF shader directly.
- The SDF shader already has basic lighting. Add material properties to `SDFPrimitiveData` and extend the fragment shader.

### Material Data Structure
- Add to `SDFPrimitiveData` in both C# and HLSL:
  ```hlsl
  struct SDFPrimitiveData {
      // ... existing fields ...
      float4 baseColor;    // RGB + alpha for transparency
      float metallic;
      float roughness;
      float ior;           // Index of refraction
      float3 emission;
  };
  ```

### Refraction is Expensive
- Double raymarching (entry + exit) for refraction is ~2x the cost.
- **Optimization**: Only do exit-point march for materials with IOR != 1.0. Skip for opaque materials.
- Consider pre-computing "thickness" for common shapes as an approximation.

### Post-Processing Integration
- URP Bloom works on the final rendered image, so it will work with the SDF output automatically.
- Add a Global Volume to the scene with:
  - Bloom: threshold 1.0, intensity 0.5
  - Tonemapping: ACES

### Transparency Order
- Raymarching doesn't handle depth sorting. Objects render back-to-front naturally, but blend modes are tricky.
- **Solution**: Use alpha blending for now. True transparency requires depth buffer compositing which is complex.

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
