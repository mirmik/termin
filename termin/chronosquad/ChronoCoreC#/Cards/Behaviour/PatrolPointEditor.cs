using UnityEngine;

public class PatrolPointEditor : MonoBehaviour
{
    Patrol patrol;
    float StandTime;

    GameObject _sphere;
    GameObject _cylinder;

    public int Index { get; set; }
    public event System.Action<PatrolPointEditor> OnEditorPointMoved;

    public void Init(Patrol patrol, float standTime)
    {
        this.patrol = patrol;
        _sphere = transform.Find("Sphere").gameObject;
        _cylinder = transform.Find("Cylinder").gameObject;
        StandTime = standTime;

        if (StandTime == 0)
            _cylinder.SetActive(false);
    }

    public void MoveEditorPoint(Vector3 position)
    {
        Debug.Assert(patrol != null);
        transform.position = position;
        OnEditorPointMoved?.Invoke(this);
    }

    public void RemoveThis()
    {
        Debug.Assert(patrol != null);
        patrol.RemovePoint(Index);
    }

    public void CreateOneYet()
    {
        Debug.Assert(patrol != null);
        patrol.CreateOneYet(Index);
    }

    public void SetRotation(Quaternion q)
    {
        transform.rotation = q;
        patrol.SetPointRotation(q, Index);
    }
}
