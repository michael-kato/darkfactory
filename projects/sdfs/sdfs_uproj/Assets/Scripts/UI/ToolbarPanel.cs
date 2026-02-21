using UnityEngine;
using UnityEngine.UIElements;

public class ToolbarPanel : MonoBehaviour
{
    [SerializeField] private SDFSceneManager sceneManager;
    [SerializeField] private PropertyInspector propertyInspector;
    
    private Button _sphereButton;
    private Button _boxButton;
    private Button _cylinderButton;
    private Button _coneButton;
    private Button _torusButton;
    private Button _capsuleButton;
    private Button _deleteButton;
    private Button _clearAllButton;
    private DropdownField _blendModeDropdown;

    private void OnEnable()
    {
        var root = GetComponent<UIDocument>().rootVisualElement;
        
        _sphereButton = root.Q<Button>("SphereButton");
        _boxButton = root.Q<Button>("BoxButton");
        _cylinderButton = root.Q<Button>("CylinderButton");
        _coneButton = root.Q<Button>("ConeButton");
        _torusButton = root.Q<Button>("TorusButton");
        _capsuleButton = root.Q<Button>("CapsuleButton");
        _deleteButton = root.Q<Button>("DeleteButton");
        _clearAllButton = root.Q<Button>("ClearAllButton");
        _blendModeDropdown = root.Q<DropdownField>("BlendModeDropdown");

        _sphereButton?.RegisterCallback<ClickEvent>(e => AddPrimitive(SDFPrimitiveType.Sphere));
        _boxButton?.RegisterCallback<ClickEvent>(e => AddPrimitive(SDFPrimitiveType.Box));
        _cylinderButton?.RegisterCallback<ClickEvent>(e => AddPrimitive(SDFPrimitiveType.Cylinder));
        _coneButton?.RegisterCallback<ClickEvent>(e => AddPrimitive(SDFPrimitiveType.Cone));
        _torusButton?.RegisterCallback<ClickEvent>(e => AddPrimitive(SDFPrimitiveType.Torus));
        _capsuleButton?.RegisterCallback<ClickEvent>(e => AddPrimitive(SDFPrimitiveType.Capsule));
        _deleteButton?.RegisterCallback<ClickEvent>(e => DeleteSelected());
        _clearAllButton?.RegisterCallback<ClickEvent>(e => ClearAll());
        _blendModeDropdown?.RegisterCallback<ChangeEvent<string>>(OnBlendModeChanged);
    }

    private void AddPrimitive(SDFPrimitiveType type)
    {
        if (sceneManager != null)
        {
            sceneManager.AddPrimitive(type, Vector3.zero, Vector3.one);
        }
    }

    private void OnBlendModeChanged(ChangeEvent<string> evt)
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            int mode = evt.newValue switch
            {
                "Union" => 0,
                "Subtraction" => 1,
                "Intersection" => 2,
                _ => 0
            };
            sceneManager.SelectedPrimitive.BlendMode = (BlendMode)mode;
        }
    }

    private void DeleteSelected()
    {
        if (sceneManager?.SelectedPrimitive != null)
        {
            sceneManager.RemovePrimitive(sceneManager.SelectedPrimitive);
            sceneManager.DeselectAll();
        }
    }

    private void ClearAll()
    {
        if (sceneManager != null)
        {
            sceneManager.ClearAllPrimitives();
        }
    }

    private void Update()
    {
        bool hasSelection = sceneManager?.SelectedPrimitive != null;
        
        if (_deleteButton != null) _deleteButton.SetEnabled(hasSelection);
        
        if (_blendModeDropdown != null && hasSelection)
        {
            _blendModeDropdown.SetEnabled(true);
            _blendModeDropdown.value = sceneManager.SelectedPrimitive.BlendMode.ToString();
        }
        else if (_blendModeDropdown != null)
        {
            _blendModeDropdown.SetEnabled(false);
        }
    }
}
