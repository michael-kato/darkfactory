using UnityEngine;
using UnityEngine.UIElements;

public class PerformanceHUD : MonoBehaviour
{
    [SerializeField] private SDFSceneManager sceneManager;
    
    private Label _fpsText;
    private Label _primitiveCountText;
    private Label _drawCallsText;

    private float _deltaTime;
    private int _frameCount;
    private float _fpsUpdateInterval = 0.5f;
    private float _fpsTimer;

    private void OnEnable()
    {
        var root = GetComponent<UIDocument>().rootVisualElement;
        
        _fpsText = root.Q<Label>("FPSText");
        _primitiveCountText = root.Q<Label>("PrimitiveCountText");
        _drawCallsText = root.Q<Label>("DrawCallsText");
    }

    private void Update()
    {
        _deltaTime += (Time.deltaTime - _deltaTime) * 0.1f;
        _frameCount++;
        _fpsTimer += Time.deltaTime;

        if (_fpsTimer >= _fpsUpdateInterval)
        {
            float fps = _frameCount / _fpsTimer;
            if (_fpsText != null)
                _fpsText.text = $"FPS: {fps:0}";
            _frameCount = 0;
            _fpsTimer = 0;
        }

        if (sceneManager != null && _primitiveCountText != null)
        {
            _primitiveCountText.text = $"Primitives: {sceneManager.PrimitiveCount}";
        }

        if (_drawCallsText != null)
        {
            string pipelineName = UnityEngine.Rendering.GraphicsSettings.defaultRenderPipeline != null ? 
                "URP" : "Built-in";
            _drawCallsText.text = $"Draw Calls: {pipelineName}";
        }
    }
}
