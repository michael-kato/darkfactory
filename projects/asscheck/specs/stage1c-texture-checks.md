# Spec: Stage 1c — Texture Checks

## Goal
Validate all textures referenced by materials in the Blender scene: resolution limits,
power-of-two dimensions, missing references, texture count per material, channel
count/bit depth, and color space assignment. Uses bpy image data and optionally Pillow
for deeper image inspection.

## Depends On
- `stage0-qa-schema.md`
- `stage1a-geometry-checks.md` (BlenderContext pattern)

## Acceptance Criteria

1. Module `pipeline/stage1/texture.py` exports `check_textures(context: BlenderContext, config: TextureConfig) -> StageResult`.

2. **`TextureConfig` dataclass**:
   ```python
   @dataclass
   class TextureConfig:
       max_resolution_standard: int   # default 2048
       max_resolution_hero: int       # default 4096
       is_hero_asset: bool            # if True, use hero limit
       max_textures_per_material: int # default 8
   ```

3. **Checks performed**:

   | Check name | Logic | Fail condition |
   |---|---|---|
   | `missing_textures` | Walk all materials → all node inputs → Image Texture nodes. Check `bpy.data.images[name].filepath` resolves to a real file. | Count of broken references > 0 |
   | `resolution_limit` | For each loaded image: check `image.size[0]` and `image.size[1]`. Apply hero vs standard limit. | Any dimension exceeds limit |
   | `power_of_two` | Width and height must each be a power of two (`n & (n-1) == 0`, n > 0). | Any non-PoT dimension |
   | `texture_count` | Count Image Texture nodes per material. | Any material exceeds `max_textures_per_material` |
   | `channel_depth` | `image.depth` — expected: 24 (RGB 8-bit) or 32 (RGBA 8-bit) for standard maps. Flag 16-bit and HDR as WARNING (not FAIL). | Unexpected depth (WARNING only) |
   | `color_space` | Verify `image.colorspace_settings.name`. Albedo/diffuse → `"sRGB"`. Roughness, metallic, normal, AO maps → `"Non-Color"` or `"Linear"`. Map type is inferred from socket name or texture name containing keywords: `albedo/diffuse/color`, `normal`, `rough/roughness`, `metal/metallic`, `ao/ambient_occlusion`. | Color space mismatch |

4. `measured_value` semantics:
   - `missing_textures`: int (broken reference count)
   - `resolution_limit`: dict `{"violations": [{"name": str, "size": [w, h], "limit": int}]}`
   - `power_of_two`: dict `{"violations": [{"name": str, "size": [w, h]}]}`
   - `texture_count`: dict `{"max": int, "material": str}` for the worst offender
   - `channel_depth`: dict `{"images": [{"name": str, "depth": int}]}`
   - `color_space`: dict `{"violations": [{"name": str, "expected": str, "actual": str}]}`

5. Color space check is `CheckStatus.WARNING` (not FAIL) — color space misconfiguration
   causes rendering artifacts but is detected and surfaced for human review.

6. Returns `StageResult(name="texture", ...)`.

## Tests

**Unit tests** (`tests/test_stage1c_texture.py`) — mock image objects as simple dataclasses:
- 2048×2048 image, standard asset → `resolution_limit` passes
- 4096×4096 image, standard (non-hero) asset → `resolution_limit` fails
- 4096×4096 image, hero asset → passes
- 512×512 → PoT check passes
- 512×384 → PoT check fails (384 not PoT)
- 0×0 image → PoT check fails
- Missing file reference → `missing_textures` fails
- albedo image with colorspace `"Non-Color"` → `color_space` warning
- roughness image with colorspace `"sRGB"` → `color_space` warning
- 10 Image Texture nodes on one material with `max_textures_per_material=8` → fails

**Integration test** (`blender_tests/test_stage1c_blender.py`):
- Load sample glTF, run texture checks, assert no crash and valid JSON result

## Out of Scope
- Texture content analysis (albedo value range — that's stage1d PBR)
- Texture auto-resizing (stage2)
- VRAM calculation (stage1f performance estimates)
