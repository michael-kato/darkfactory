using UnityEngine;
using UnityEngine.UIElements;

public class ToolbarPanel : MonoBehaviour
{
    [SerializeField] private SDFSceneManager sceneManager;
    [SerializeField] private PropertyInspector propertyInspector;
    
    private Button _deleteButton;
    private DropdownField _blendModeDropdown;

    private void OnEnable()
    {
        var root = GetComponent<UIDocument>().rootVisualElement;
        
        _deleteButton = root.Q<Button>("DeleteButton");
        _blendModeDropdown = root.Q<DropdownField>("BlendModeDropdown");

        _deleteButton?.RegisterCallback<ClickEvent>(e => DeleteSelected());
        _blendModeDropdown?.RegisterCallback<ChangeEvent<string>>(OnBlendModeChanged);
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
            Destroy(sceneManager.SelectedPrimitive.gameObject);
            sceneManager.DeselectAll();
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
