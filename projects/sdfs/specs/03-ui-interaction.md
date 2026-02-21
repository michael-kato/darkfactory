# Spec: UI & Interaction System

## Goal
Add a toolbar UI for adding/editing primitives and viewport interaction (orbit, zoom, primitive selection).

## Depends On
- `02-sdf-primitives.md`

## Implementation Notes (Lessons Learned)

### Architecture Decisions
- **UI Framework**: Use UI Toolkit (UIElements) - not legacy UI. UXML files required for runtime UI.
- **Material Setup**: Never reference `Sprites-Default` or other built-in materials in scene. SDFRenderer creates its own material from shader at runtime via `new Material(Shader.Find("SDF/Render"))`.
- **Input Handling**: OrbitCamera must handle Input System vs Legacy Input conflict. Wrap legacy Input calls with `#if UNITY_EDITOR` or check `EditorApplication.isPlaying`.

### SDF Primitives Visualization
- **Problem**: Users can't see SDF shapes in Scene view
- **Solution**: Each `SDFPrimitive` component MUST have `[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]`. At runtime (Awake), create a transparent mesh that matches the SDF type so users can position/scale in editor.
- **Selection Feedback**: Change material color on selection (orange = selected, blue = unselected)

### Shader/Rendering Pipeline
- **Fullscreen Quad**: Don't use `OnRenderImage` alone - create a child quad parented to camera that scales with FOV. Quad should be positioned at z=1 relative to camera, scaled to match view frustum.
- **Camera Parameters**: Pass `_InverseViewProjection` matrix to shader for proper ray direction calculation. Don't rely on worldPos from vertex shader alone.
- **Debug Colors**: Add fallback colors in shader (e.g., red = no primitives, blue = miss) to diagnose rendering issues.

### ComputeBuffer Sync
- The shader receives `_PrimitiveCount` and `_Primitives` buffer from `SDFSceneManager`.
- If shader shows "no primitives" color, verify:
  1. `SDFSceneManager` is in scene and enabled
  2. `SDFRenderer.sceneManager` reference is set
  3. `SDFPrimitive` GameObjects exist in scene with correct component

### Scene Setup Requirements
- **SDFSceneManager**: GameObject with `SDFSceneManager` component
- **SDFRenderer**: GameObject with `SDFRenderer` component, linked to SceneManager
- **Main Camera**: Must exist. `SDFRenderer` will find it or create one.
- **UI Panels**: Each UI panel needs:
  - `UIDocument` component (for UIElements)
  - Script component for logic (e.g., `ToolbarPanel`)
  - Both must reference `SDFSceneManager`

## Acceptance Criteria

1. Toolbar panel in `Assets/Scripts/UI/` with UXML:
   - Buttons for each primitive type → adds to scene
   - Dropdown for blend mode selection on selected primitive
   - Delete button to remove selected primitive
   - Clear all button

2. Property inspector panel:
   - Shows selected primitive properties
   - Sliders for position (X/Y/Z), scale (uniform)
   - Slider for blend radius
   - Real-time update as values change

3. Viewport controls:
   - Right-click drag: Orbit camera
   - Scroll: Zoom in/out
   - Left-click on SDF surface: Select primitive
   - Middle-click drag: Pan

4. Performance HUD overlay:
   - FPS counter (top-left)
   - Primitive count
   - Draw calls

5. Integration with `SDFSceneManager`:
   - Primitive list stays in sync with scene
   - Selection highlights in viewport (via MeshRenderer color change)

6. Editor Visualization:
   - Each SDFPrimitive displays a matching Unity primitive in Scene view
   - Primitives can be moved/scaled using standard Unity transform gizmos
   - Changes sync to shader in real-time during Play mode

## Out of Scope
- Physics interaction (poking, dragging)
- Export functionality
- Advanced materials

## Potential Issues for Future Specs

### 04-faux-physics.md
- **Issue**: ComputeShader vs main thread. Physics simulation should run on GPU via ComputeShader for performance, but interaction callbacks need CPU side.
- **Recommendation**: Use ComputeShader for SDF evaluation, buffer results back to CPU only when needed for selection/gizmos.

### 05-materials.md
- **Issue**: URP material system vs custom raymarching. Standard URP shaders won't work with raymarching.
- **Recommendation**: Keep material system separate - extend SDF shader with material properties (color, metallic, roughness) rather than trying to use URP lit materials.

### 06-export.md
- **Issue**: Mesh generation from SDF is computationally expensive. Real-time mesh extraction at 60fps is hard.
- **Recommendation**: Consider ComputeShader-based mesh generation with async readback, or offer "bake" step for export rather than real-time.
