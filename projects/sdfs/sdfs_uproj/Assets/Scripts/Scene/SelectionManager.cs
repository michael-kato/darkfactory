using UnityEngine;

public class SelectionManager : MonoBehaviour
{
    [SerializeField] private SDFSceneManager sceneManager;

    private void Start()
    {
        if (sceneManager != null)
        {
            sceneManager.OnSelectionChanged += OnSelectionChanged;
        }
    }

    private void OnSelectionChanged(SDFPrimitive selectedPrimitive)
    {
        SDFPrimitive[] allPrimitives = FindObjectsOfType<SDFPrimitive>();
        foreach (var prim in allPrimitives)
        {
            prim.IsSelected = (prim == selectedPrimitive);
        }
    }

    private void OnDestroy()
    {
        if (sceneManager != null)
        {
            sceneManager.OnSelectionChanged -= OnSelectionChanged;
        }
    }
}
