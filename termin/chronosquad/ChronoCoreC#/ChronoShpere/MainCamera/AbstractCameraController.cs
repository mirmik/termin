using UnityEngine;
using System.Runtime.InteropServices;

public abstract class AbstractCameraController : MonoBehaviour
{
    public Transform reference_frame;

    protected static AbstractCameraController _instance = null;

    public static AbstractCameraController Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = GameObject.FindFirstObjectByType<CameraController>();
            }
            return _instance;
        }
    }

    //#if UNITY_STANDALONE_WIN
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT lpPoint);

    //#endif


    public virtual void move_forward(float speed) { }

    public virtual void ChangeCameraFrame(Transform frame)
    {
        //Camera.main.transform.parent = frame;
        reference_frame = frame;
    }

    public virtual void ChangeReferencedFrame(Transform frame)
    {
        reference_frame = frame;
    }

    public Matrix4x4 GetInverseProjectionMatrix()
    {
        Matrix4x4 mainProjectionMatrix = GL.GetGPUProjectionMatrix(
            Camera.main.projectionMatrix,
            false
        );
        return mainProjectionMatrix.inverse;
    }

    public Matrix4x4 GetInverseViewMatrix()
    {
        Matrix4x4 mainViewMatrix = Camera.main.worldToCameraMatrix;
        return mainViewMatrix.inverse;
    }

    public abstract void LateUpdateImpl();

    public virtual ObjectId ReferenceObjectId()
    {
        return default(ObjectId);
    }

    public abstract void TeleportToNewCenter(Vector3 pos, Vector3 up);

    public void TeleportToNewCenterWithNewReference(
        Vector3 pos,
        Transform new_reference_frame,
        Vector3 up
    )
    {
        TeleportToNewCenter(pos, up);
        ChangeReferencedFrame(new_reference_frame);
        TeleportToNewCenter(pos, up);
    }
}
