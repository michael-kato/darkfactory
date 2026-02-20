# Spec: Stage 1d — PBR Material Validation

## Goal
Validate PBR material compliance: workflow type, albedo/metalness/roughness value ranges,
normal map validity, material slot count, and Principled BSDF node graph structure.
Uses bpy node graph introspection and optional pixel sampling via Pillow.

## Depends On
- `stage0-qa-schema.md`
- `stage1a-geometry-checks.md` (BlenderContext pattern)

## Acceptance Criteria

1. Module `pipeline/stage1/pbr.py` exports `check_pbr(context: BlenderContext, config: PBRConfig) -> StageResult`.

2. **`PBRConfig` dataclass**:
   ```python
   @dataclass
   class PBRConfig:
       max_material_slots: int          # default 3
       albedo_min_srgb: int             # default 30
       albedo_max_srgb: int             # default 240
       albedo_sample_count: int         # pixels sampled per image, default 1000
       metalness_binary_threshold: float # values between (t, 1-t) flagged, default 0.1
   ```

3. **Checks performed**:

   | Check name | Logic | Fail condition |
   |---|---|---|
   | `pbr_workflow` | Each material must use a Principled BSDF node as its primary output. Detect spec/gloss materials (Specular BSDF or "Glossiness" socket in use). | Any material not using Principled BSDF |
   | `material_slots` | Count material slots per mesh object. | Any object exceeds `max_material_slots` |
   | `albedo_range` | Sample up to `albedo_sample_count` random pixels from the albedo/base-color texture. For non-metal pixels (metallic value ≈ 0), sRGB values must be in [`albedo_min_srgb`, `albedo_max_srgb`]. Report fraction out of range. | >5% of sampled pixels out of range |
   | `metalness_binary` | Sample metallic texture. Pixels with values in (`metalness_binary_threshold`, 1.0 - `metalness_binary_threshold`) are flagged as gradient (unusual in non-transition areas). Report fraction of gradient pixels. | >10% gradient pixels (WARNING, not FAIL) |
   | `roughness_range` | Sample roughness texture. Flag images where >50% of pixels are pure 0.0 or pure 1.0. | Either extreme dominates (WARNING) |
   | `normal_map` | For each image connected to the Normal Map node: verify colorspace is `"Non-Color"`. Sample pixels to verify blue channel dominant (mean B > mean R and mean B > mean G). Verify values are in [0,1] range after linear conversion. | Wrong colorspace, or B not dominant |
   | `node_graph` | Walk each Principled BSDF material. Flag: orphan image nodes not connected to any output, cycles in node graph, empty material slots (no nodes). | Any violation (WARNING) |

4. Pixel sampling (albedo, metalness, roughness, normal) uses Pillow (`PIL.Image`).
   If image data is packed into the .blend, use `bpy.data.images[name].pixels` directly.
   If image data is a file reference, load with Pillow.

5. `measured_value` semantics:
   - `pbr_workflow`: list of non-compliant material names
   - `material_slots`: dict `{"max": int, "object": str}`
   - `albedo_range`: dict `{"fraction_out_of_range": float, "sample_count": int}`
   - `metalness_binary`: dict `{"fraction_gradient": float}`
   - `roughness_range`: dict `{"fraction_pure_zero": float, "fraction_pure_one": float}`
   - `normal_map`: dict `{"colorspace_violations": [...], "channel_violations": [...]}`
   - `node_graph`: list of issue descriptions

6. `albedo_range`, `metalness_binary`, `roughness_range`, and `node_graph` checks use
   `CheckStatus.WARNING` (per section 6.2 — may be intentional stylistic choice).
   `pbr_workflow`, `material_slots`, and `normal_map` use `CheckStatus.FAIL` on violation.

7. Returns `StageResult(name="pbr", ...)`.

## Tests

**Unit tests** (`tests/test_stage1d_pbr.py`) — mock materials as dataclasses, mock pixel arrays as numpy arrays:
- Material with Principled BSDF → `pbr_workflow` passes
- Material without Principled BSDF → `pbr_workflow` fails
- 4 material slots, max=3 → `material_slots` fails
- Albedo pixels all in [30, 240] → `albedo_range` warning not triggered
- Albedo pixels 20% below 30 → `albedo_range` warning triggered
- Normal map with colorspace `"sRGB"` → `normal_map` fails
- Normal map with R-dominant pixels → `normal_map` fails
- Metalness values all near 0 or 1 → `metalness_binary` warning not triggered
- Metalness 50% gradient pixels → `metalness_binary` warning triggered

**Integration test** (`blender_tests/test_stage1d_blender.py`):
- Load sample glTF, run PBR checks, assert no crash and valid JSON

## Out of Scope
- Spec/gloss to metalness/roughness conversion (future)
- Texture baking (future)
- Shader node compilation or preview rendering
