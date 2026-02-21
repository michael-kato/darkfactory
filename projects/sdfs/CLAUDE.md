# SDF Editor - Project Conventions

## Stack
- Unity 6.x (2024.2+)
- Universal Render Pipeline (URP) 17.x
- C#
- Compute Shaders (HLSL)
- DOTS/ECS optional (for entity management)

## Project Structure
```
sdfs_uproj/
  Assets/
    Scenes/          - Unity scenes
    Scripts/         - C# scripts
    Shaders/         - HLSL/shader files
    Prefabs/         - Prefab assets
    Settings/        - URP/HDRP settings
  Packages/          - Unity package dependencies
  ProjectSettings/   - Unity project settings
```

## Key Technologies
- **SDF**: Signed Distance Fields for primitive modeling
- **Ray Marching**: GPU-based rendering via fragment shaders
- **Compute Shaders**: For SDF evaluation and faux physics
- **URP**: Universal Render Pipeline (not HDRP in current config)

## Code Conventions
- C# scripts: Standard Unity conventions (PascalCase for methods, camelCase for variables)
- Shaders: HLSL with Compute Shader support
- Use `[SerializeField]` for private serialized fields
- Use Unity's Input System (already configured)

## Test Command
```bash
./test.sh
```
Runs Unity in batch mode to verify project compiles and builds.
