using UnityEngine;

public abstract class CameraBounds : MonoBehaviour
{
    abstract public bool IsValid(Vector3 pos);
}
