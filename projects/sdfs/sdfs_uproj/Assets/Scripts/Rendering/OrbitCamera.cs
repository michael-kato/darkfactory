using UnityEngine;

public class OrbitCamera : MonoBehaviour
{
    [SerializeField] private Transform target;
    [SerializeField] private float distance = 5.0f;
    [SerializeField] private float sensitivity = 5.0f;
    [SerializeField] private float minDistance = 1.0f;
    [SerializeField] private float maxDistance = 20.0f;
    [SerializeField] private float minPitch = -89f;
    [SerializeField] private float maxPitch = 89f;
    [SerializeField] private SDFSceneManager sceneManager;

    private float _yaw;
    private float _pitch;
    private Vector3 _targetPosition;

    private void Start()
    {
        Vector3 angles = transform.eulerAngles;
        _yaw = angles.y;
        _pitch = angles.x;

        if (target != null)
        {
            _targetPosition = target.position;
        }
        else
        {
            _targetPosition = Vector3.zero;
        }

        UpdateCameraPosition();
    }

    private void Update()
    {
#if UNITY_EDITOR
        if (!UnityEditor.EditorApplication.isPlaying) return;
#endif
        
        if (Input.GetMouseButton(1))
        {
            _yaw += Input.GetAxis("Mouse X") * sensitivity;
            _pitch -= Input.GetAxis("Mouse Y") * sensitivity;
            _pitch = Mathf.Clamp(_pitch, minPitch, maxPitch);
        }

        float scroll = Input.GetAxis("Mouse ScrollWheel");
        distance -= scroll * sensitivity * 2f;
        distance = Mathf.Clamp(distance, minDistance, maxDistance);

        if (Input.GetMouseButton(2) || (Input.GetMouseButton(0) && Input.GetKey(KeyCode.LeftAlt)))
        {
            float moveX = -Input.GetAxis("Mouse X") * sensitivity * 0.1f * distance;
            float moveY = -Input.GetAxis("Mouse Y") * sensitivity * 0.1f * distance;
            
            Quaternion rotation = Quaternion.Euler(0, _yaw, 0);
            _targetPosition += rotation * new Vector3(moveX, moveY, 0);
        }

        if (Input.GetMouseButtonDown(0) && !Input.GetKey(KeyCode.LeftAlt))
        {
            HandlePrimitiveSelection();
        }

        UpdateCameraPosition();
    }

    private void HandlePrimitiveSelection()
    {
        if (sceneManager == null) return;

        Ray ray = GetComponent<Camera>().ScreenPointToRay(Input.mousePosition);
        SDFPrimitive[] primitives = FindObjectsOfType<SDFPrimitive>();
        
        SDFPrimitive closestPrimitive = null;
        float closestDistance = float.MaxValue;

        foreach (var prim in primitives)
        {
            float primDistance = GetPrimitiveDistance(prim, ray);
            if (primDistance > 0 && primDistance < closestDistance)
            {
                closestDistance = primDistance;
                closestPrimitive = prim;
            }
        }

        sceneManager.SelectPrimitive(closestPrimitive);
    }

    private float GetPrimitiveDistance(SDFPrimitive prim, Ray ray)
    {
        Vector3 primPos = prim.Position;
        float primScale = prim.Scale.x * 0.5f;

        switch (prim.Type)
        {
            case SDFPrimitiveType.Sphere:
                return GetSphereDistance(primPos, primScale, ray);
            case SDFPrimitiveType.Box:
                return GetBoxDistance(primPos, prim.Scale * 0.5f, ray);
            default:
                Vector3 toPrimitive = primPos - ray.origin;
                float dot = Vector3.Dot(toPrimitive, ray.direction);
                if (dot < 0) return -1;
                Vector3 closestPoint = ray.origin + ray.direction * dot;
                float dist = Vector3.Distance(closestPoint, primPos);
                return dist < primScale * 1.5f ? dot : -1;
        }
    }

    private float GetSphereDistance(Vector3 center, float radius, Ray ray)
    {
        Vector3 oc = ray.origin - center;
        float a = Vector3.Dot(ray.direction, ray.direction);
        float b = 2.0f * Vector3.Dot(oc, ray.direction);
        float c = Vector3.Dot(oc, oc) - radius * radius;
        float discriminant = b * b - 4 * a * c;

        if (discriminant > 0)
        {
            float t = (-b - Mathf.Sqrt(discriminant)) / (2.0f * a);
            if (t > 0) return t;
        }
        return -1;
    }

    private float GetBoxDistance(Vector3 center, Vector3 halfExtents, Ray ray)
    {
        Vector3 invDir = new Vector3(1f / ray.direction.x, 1f / ray.direction.y, 1f / ray.direction.z);
        Vector3 t0 = new Vector3((center.x - halfExtents.x - ray.origin.x) * invDir.x,
                                   (center.y - halfExtents.y - ray.origin.y) * invDir.y,
                                   (center.z - halfExtents.z - ray.origin.z) * invDir.z);
        Vector3 t1 = new Vector3((center.x + halfExtents.x - ray.origin.x) * invDir.x,
                                   (center.y + halfExtents.y - ray.origin.y) * invDir.y,
                                   (center.z + halfExtents.z - ray.origin.z) * invDir.z);
        
        Vector3 tmin = Vector3.Min(t0, t1);
        Vector3 tmax = Vector3.Max(t0, t1);
        
        float tNear = Mathf.Max(Mathf.Max(tmin.x, tmin.y), tmin.z);
        float tFar = Mathf.Min(Mathf.Min(tmax.x, tmax.y), tmax.z);
        
        if (tFar < 0 || tNear > tFar) return -1;
        return tNear > 0 ? tNear : tFar;
    }

    private void UpdateCameraPosition()
    {
        Quaternion rotation = Quaternion.Euler(_pitch, _yaw, 0);
        Vector3 direction = new Vector3(0, 0, -distance);
        
        transform.position = _targetPosition + rotation * direction;
        transform.LookAt(_targetPosition);
    }

    public void SetTarget(Transform newTarget)
    {
        target = newTarget;
        if (newTarget != null)
        {
            _targetPosition = newTarget.position;
        }
    }
}
