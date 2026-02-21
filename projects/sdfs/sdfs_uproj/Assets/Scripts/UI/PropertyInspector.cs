using UnityEngine;
using UnityEngine.UIElements;

public class PropertyInspector : MonoBehaviour
{
    [SerializeField] private SDFSceneManager sceneManager;
    
    private VisualElement _contentPanel;
    
    private Slider _positionXSlider;
    private Slider _positionYSlider;
    private Slider _positionZSlider;
    private Slider _scaleSlider;
    private Slider _blendRadiusSlider;

    private Label _positionXValue;
    private Label _positionYValue;
    private Label _positionZValue;
    private Label _scaleValue;
    private Label _blendRadiusValue;

    private const float POSITION_RANGE = 10f;
    private const float SCALE_MIN = 0.1f;
    private const float SCALE_MAX = 5f;
    private const float BLEND_MIN = 0f;
    private const float BLEND_MAX = 2f;

    private void OnEnable()
    {
        var root = GetComponent<UIDocument>().rootVisualElement;
        
        _contentPanel = root.Q<VisualElement>("ContentPanel");
        
        _positionXSlider = root.Q<Slider>("PositionXSlider");
        _positionYSlider = root.Q<Slider>("PositionYSlider");
        _positionZSlider = root.Q<Slider>("PositionZSlider");
        _scaleSlider = root.Q<Slider>("ScaleSlider");
        _blendRadiusSlider = root.Q<Slider>("BlendRadiusSlider");

        _positionXValue = root.Q<Label>("PositionXValue");
        _positionYValue = root.Q<Label>("PositionYValue");
        _positionZValue = root.Q<Label>("PositionZValue");
        _scaleValue = root.Q<Label>("ScaleValue");
        _blendRadiusValue = root.Q<Label>("BlendRadiusValue");

        SetupSliders();
    }

    private void SetupSliders()
    {
        if (_positionXSlider != null)
        {
            _positionXSlider.lowValue = -POSITION_RANGE;
            _positionXSlider.highValue = POSITION_RANGE;
            _positionXSlider.RegisterCallback<ChangeEvent<float>>(OnPositionXChanged);
        }
        if (_positionYSlider != null)
        {
            _positionYSlider.lowValue = -POSITION_RANGE;
            _positionYSlider.highValue = POSITION_RANGE;
            _positionYSlider.RegisterCallback<ChangeEvent<float>>(OnPositionYChanged);
        }
        if (_positionZSlider != null)
        {
            _positionZSlider.lowValue = -POSITION_RANGE;
            _positionZSlider.highValue = POSITION_RANGE;
            _positionZSlider.RegisterCallback<ChangeEvent<float>>(OnPositionZChanged);
        }
        if (_scaleSlider != null)
        {
            _scaleSlider.lowValue = SCALE_MIN;
            _scaleSlider.highValue = SCALE_MAX;
            _scaleSlider.RegisterCallback<ChangeEvent<float>>(OnScaleChanged);
        }
        if (_blendRadiusSlider != null)
        {
            _blendRadiusSlider.lowValue = BLEND_MIN;
            _blendRadiusSlider.highValue = BLEND_MAX;
            _blendRadiusSlider.RegisterCallback<ChangeEvent<float>>(OnBlendRadiusChanged);
        }
    }

    private void OnPositionXChanged(ChangeEvent<float> evt)
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            Vector3 pos = sceneManager.SelectedPrimitive.Position;
            pos.x = evt.newValue;
            sceneManager.SelectedPrimitive.Position = pos;
            sceneManager.SelectedPrimitive.SyncFromTransform();
            UpdatePositionLabels();
        }
    }

    private void OnPositionYChanged(ChangeEvent<float> evt)
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            Vector3 pos = sceneManager.SelectedPrimitive.Position;
            pos.y = evt.newValue;
            sceneManager.SelectedPrimitive.Position = pos;
            sceneManager.SelectedPrimitive.SyncFromTransform();
            UpdatePositionLabels();
        }
    }

    private void OnPositionZChanged(ChangeEvent<float> evt)
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            Vector3 pos = sceneManager.SelectedPrimitive.Position;
            pos.z = evt.newValue;
            sceneManager.SelectedPrimitive.Position = pos;
            sceneManager.SelectedPrimitive.SyncFromTransform();
            UpdatePositionLabels();
        }
    }

    private void OnScaleChanged(ChangeEvent<float> evt)
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            sceneManager.SelectedPrimitive.Scale = Vector3.one * evt.newValue;
            sceneManager.SelectedPrimitive.SyncFromTransform();
            if (_scaleValue != null)
                _scaleValue.text = evt.newValue.ToString("F2");
        }
    }

    private void OnBlendRadiusChanged(ChangeEvent<float> evt)
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            sceneManager.SelectedPrimitive.BlendRadius = evt.newValue;
            if (_blendRadiusValue != null)
                _blendRadiusValue.text = evt.newValue.ToString("F2");
        }
    }

    private void UpdatePositionLabels()
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            Vector3 pos = sceneManager.SelectedPrimitive.Position;
            if (_positionXValue != null) _positionXValue.text = pos.x.ToString("F2");
            if (_positionYValue != null) _positionYValue.text = pos.y.ToString("F2");
            if (_positionZValue != null) _positionZValue.text = pos.z.ToString("F2");
        }
    }

    private void Update()
    {
        bool hasSelection = sceneManager?.SelectedPrimitive != null;
        
        if (_contentPanel != null)
            _contentPanel.style.display = hasSelection ? DisplayStyle.Flex : DisplayStyle.None;

        if (hasSelection)
        {
            SDFPrimitive prim = sceneManager.SelectedPrimitive;
            
            if (_positionXSlider != null) _positionXSlider.value = prim.Position.x;
            if (_positionYSlider != null) _positionYSlider.value = prim.Position.y;
            if (_positionZSlider != null) _positionZSlider.value = prim.Position.z;
            if (_scaleSlider != null) _scaleSlider.value = prim.Scale.x;
            if (_blendRadiusSlider != null) _blendRadiusSlider.value = prim.BlendRadius;

            UpdatePositionLabels();
            if (_scaleValue != null) _scaleValue.text = prim.Scale.x.ToString("F2");
            if (_blendRadiusValue != null) _blendRadiusValue.text = prim.BlendRadius.ToString("F2");
        }
    }
}
