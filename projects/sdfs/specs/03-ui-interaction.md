# Spec: UI & Interaction System

## Goal
Add a toolbar UI for adding/editing primitives and viewport interaction (orbit, zoom, primitive selection).

## Depends On
- `02-sdf-primitives.md`

## Acceptance Criteria

1. Toolbar panel in `Assets/Scripts/UI/`:
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
   - Selection highlights in viewport

## Out of Scope
- Physics interaction (poking, dragging)
- Export functionality
- Advanced materials
