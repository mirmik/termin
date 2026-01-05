using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class InterestPoint : MonoBehaviour
{
    public List<InterestPoint> links = new List<InterestPoint>();

    // Start is called before the first frame update
    void Start() { }

    // Update is called once per frame
    void Update() { }

    public ReferencedPoint GetReferencedPoint()
    {
        return new ReferencedPoint(transform.position, null);
    }
}
