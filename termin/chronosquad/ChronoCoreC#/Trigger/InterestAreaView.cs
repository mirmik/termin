using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class InterestAreaView : MonoBehaviour
{
    public string Name = "InterestArea";

    ChronoSphere chronoSphere;
    AreaOfInterest areaOfInterest;

    MyList<InterestPoint> insidePoints = new MyList<InterestPoint>();

    void Start()
    {
        chronoSphere = GameCore.Chronosphere();
        areaOfInterest = chronoSphere.GetOrCreateAreaOfInterest(Name);
        insidePoints = FindAllInterestPointsInsideThisArea();
        areaOfInterest.AddInterestPointsViews(insidePoints);
    }

    public bool IsPointInsideArea(InterestPoint point)
    {
        var incoords = transform.InverseTransformPoint(point.transform.position);
        var size = transform.localScale;
        var halfsize = new Vector3(1, 1, 1) / 2;
        if (
            incoords.x > -halfsize.x
            && incoords.x < halfsize.x
            && incoords.y > -halfsize.y
            && incoords.y < halfsize.y
            && incoords.z > -halfsize.z
            && incoords.z < halfsize.z
        )
        {
            return true;
        }
        return false;
    }

    public InterestPoint[] FindAllInterestPointsOnScene()
    {
        InterestPoint[] result = GameObject.FindObjectsByType<InterestPoint>(
            FindObjectsSortMode.None
        );
        return result;
    }

    public MyList<InterestPoint> FindAllInterestPointsInsideThisArea()
    {
        MyList<InterestPoint> result = new MyList<InterestPoint>();
        foreach (InterestPoint point in FindAllInterestPointsOnScene())
        {
            if (IsPointInsideArea(point))
            {
                result.Add(point);
            }
        }
        return result;
    }
}
