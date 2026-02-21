# Darkfactory Project: Interactive SDF Primitive 3D Modeling System in Unity

## Project Overview
The Darkfactory project aims to develop an interactive 3D modeling system within Unity, leveraging Signed Distance Fields (SDFs) for primitive shape creation and manipulation. Users can intuitively combine basic 3D primitives (e.g., spheres, cubes, cylinders) using SDF operations to form complex models. The system emphasizes a smoothed, subdivided aesthetic with organic blending, simulating jello-like wiggling and rippling through a faux physics engine. All SDF computations will run entirely on the GPU for optimal performance, utilizing Unity 6's advanced rendering features such as Data-Oriented Technology Stack (DOTS), Entity Component System (ECS), and GPU-driven pipelines where applicable. The result will be a highly optimized, visually captivating experience with refractive and faintly glowing materials, suitable for real-time interactive applications like creative tools, games, or visualizations.

**Project Goals:**
- Enable real-time user interaction for shape combination and manipulation.
- Achieve high frame rates (target: 60+ FPS on mid-range hardware) through GPU acceleration.
- Deliver an aesthetically pleasing "organic" look with dynamic animations and advanced shading.

**Target Platforms:** Primarily desktop (Windows/Mac), with potential for VR/AR extensions. Built on Unity 6.x.

**Development Timeline Estimate:** 
- Prototype: 4-6 weeks.
- Core Features: 8-12 weeks.
- Optimization & Polish: 4-6 weeks.
- Total: 3-6 months for MVP.

## Key Features
### SDF Primitive Modeling
- **Primitives Supported:** Sphere, Cube/Box, Cylinder, Cone, Torus, Capsule. Extensible for custom primitives via shader code.
- **Combination Operations:** Union, Intersection, Subtraction, with smooth blending (e.g., using exponential smoothing functions for metaball-like effects).
- **User Interaction:** 
  - Drag-and-drop interface for adding/removing primitives.
  - Real-time editing of position, scale, rotation, and blending parameters via Unity's UI Toolkit or IMGUI.
  - Hierarchical grouping for complex assemblies (e.g., parent-child relationships for compound shapes).
- **Smoothed Subdivided Look:** Automatic application of subdivision-like smoothing via SDF distance-based interpolation, avoiding traditional mesh subdivision for performance. Target resolution equivalent to level 3-4 Catmull-Clark subdivision without CPU overhead.

### Faux Physics Simulation
- **Jello-Like Dynamics:** Shapes exhibit wiggling and rippling in response to user input (e.g., poking, dragging) or environmental triggers (e.g., gravity simulation).
- **Implementation:** A simplified, GPU-based spring-mass system or wave propagation simulated via compute shaders. No full physics engine (e.g., avoid PhysX); instead, use procedural noise (Perlin/Simplex) modulated over time for ripple effects, combined with damped oscillations for wiggle.
- **Parameters:** User-adjustable stiffness, damping, and amplitude for customization. Ensure stability to prevent visual artifacts like exploding shapes.

### Rendering and Visualization
- **GPU-Only SDF Evaluation:** All distance field computations performed in compute shaders or fragment shaders, using Unity's Render Graph API for efficient pipeline management.
- **Materials and Effects:**
  - **Refraction:** Simulate glass-like or watery distortion using ray marching within the SDF, with index of refraction (IOR) controls (default: 1.33 for water-like feel).
  - **Faint Glowing:** Emissive materials with bloom post-processing, using HDRP (High Definition Render Pipeline) for physically-based rendering. Glow intensity modulated by shape dynamics (e.g., brighter during ripples).
  - **Additional Shaders:** Subsurface scattering for organic feel, ambient occlusion via SDF-based approximations.
- **Visual Style:** Ethereal, dream-like aesthetic with soft lighting, volumetric fog, and color gradients (e.g., pastel hues fading to neon glows).

### User Interface and Controls
- **Interactive Canvas:** 3D viewport with orbit/zoom controls, integrated with Unity's Scene View tools.
- **Toolbar:** Buttons for primitive selection, operation modes, physics tweaks, and export options (e.g., to OBJ/GLTF for external use).
- **Performance HUD:** Real-time display of FPS, GPU usage, and primitive count to aid optimization during use.

### Export and Integration
- **Output Formats:** Export combined SDF as a mesh (via marching cubes algorithm on GPU), shader code, or serialized data for runtime use.
- **Extensibility:** API hooks for scripting (C#) to integrate with other Unity projects.

## Technical Requirements
### Hardware/Software
- **Unity Version:** 6.x or later, with HDRP enabled.
- **GPU Requirements:** DirectX 12 / Vulkan compatible (e.g., NVIDIA GTX 1060+ or equivalent) for compute shader support. Fallback to CPU for older hardware, but primary focus on GPU.
- **Dependencies:** 
  - Built-in: Unity Render Graph, Shader Graph, UI Toolkit.
  - DOTS/ECS: For managing large numbers of primitives as entities, with Burst-compiled jobs for any CPU-side prep (e.g., user input processing).
  - No external assets/plugins unless open-source and performance-verified (e.g., avoid heavy third-party SDF libraries).

### Architecture
- **Core Pipeline:**
  1. **Input Layer:** Handle user interactions via ECS entities representing primitives (position, transform data stored in components).
  2. **SDF Computation:** GPU compute shader dispatches to evaluate combined SDF. Use structured buffers for primitive data upload (limit: 1000+ primitives at 60 FPS).
  3. **Physics Simulation:** Separate compute shader for faux dynamics, updating SDF parameters per frame (e.g., offset positions with sine waves or Verlet integration).
  4. **Rendering:** Ray marching in fragment shader for final image, integrated with Unity's Custom Render Pass. Leverage GPU Instancing for efficiency.
  5. **Optimization Layer:** Use Jobs System for async data prep, and Profiler-guided tweaks.

- **Data Flow:**
  - Primitives as ECS entities → Upload to GPU buffers → Compute SDF tree → Ray march + shade.

- **Scalability:** Hierarchical SDF bounding volumes to cull computations, reducing ray steps (target: <50 steps per pixel).

## Optimization Strategies
- **GPU Focus:** All heavy lifting (SDF ops, physics) on GPU to minimize CPU bottlenecks. Use async compute queues in Unity 6 for parallel execution.
- **Performance Targets:** 
  - Primitive Count: 500+ in real-time.
  - Resolution: 1080p+ at 60 FPS.
  - Techniques: Early ray termination, adaptive sampling, LOD based on distance.
- **Profiling:** Integrate Unity Profiler and GPU capture tools. Benchmark on varied hardware.
- **Fallbacks:** If ECS/DOTS overhead is high, hybrid approach with traditional MonoBehaviour for simple scenes.
- **Memory Management:** Dynamic buffer resizing, avoid allocations per frame.

## Risks and Mitigations
- **Performance Bottlenecks:** Ray marching can be expensive; mitigate with optimized shaders and reduced march iterations.
- **Visual Artifacts:** Smoothing/blending issues; test with varied primitive combos.
- **Unity 6 Compatibility:** Monitor updates for DOTS stability; use preview packages if needed.
- **User Experience:** Ensure intuitive controls; iterate via user testing.

## Appendix: References and Inspirations
- SDF Techniques: Based on Inigo Quilez's SDF articles and GPU Gems chapters.
- Unity Features: Draw from Unity 6's GPU Resident Drawer and Compute Buffer enhancements.
- Visuals: Inspired by soft-body simulations in games like "Dreams" or "No Man's Sky" procedural effects.

This spec sheet serves as a living document and can be refined based on prototyping feedback.
