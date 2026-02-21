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

        UpdateCameraPosition();
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
