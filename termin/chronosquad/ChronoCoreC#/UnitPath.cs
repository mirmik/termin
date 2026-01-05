using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public enum UnitPathPointType
{
    StandartMesh,
    DownToBraced,
    BracedToUp,
    JumpDown,
    Unknown,
    BracedClimbingLink,
    BracedHang,
    DoorLink,
    AirStrike,
    Lean,
    ToUpstairsZone,
    FromUpstairsZone,
    UpstairsMove,
    ToBurrowZone,
    FromBurrowZone
}

public struct UnitPathPoint
{
    public ReferencedPoint position;
    public BracedCoordinates braced_coordinates; // for braced points
    public UnitPathPointType type;
    public LinkData link;
    public Vector3 normal;

    public UnitPathPoint(
        ReferencedPoint position,
        UnitPathPointType type,
        LinkData link,
        Vector3 normal = default
    )
    {
        this.position = position;
        this.type = type;
        this.braced_coordinates = default;
        this.link = link;
        this.normal = normal;
    }

    public UnitPathPoint(
        Vector3 position,
        UnitPathPointType type,
        string areaname,
        LinkData link = null,
        Vector3 normal = default
    )
    {
        this.position = new ReferencedPoint(position, areaname);
        this.type = type;
        this.link = link;
        this.braced_coordinates = default;
        this.normal = normal;
    }

    public void SetBracedCoordinates(BracedCoordinates braced_coordinates)
    {
        this.braced_coordinates = braced_coordinates;
    }

    public override string ToString()
    {
        return string.Format("Position: {0}, Type: {1}", position, type);
    }
}

// iteratible collection of points
public class UnitPath : IEnumerable<UnitPathPoint>
{
    MyList<UnitPathPoint> _passPoints;
    ReferencedPoint start_position;
    ObjectId last_frame_id;

    public void Clear()
    {
        _passPoints.Clear();
    }

    public void InitFrame(ObjectId frame_id)
    {
        last_frame_id = frame_id;
    }

    public ObjectId LastFrame()
    {
        return last_frame_id;
    }

    public void ChangeFinalPointToLean()
    {
        var last = _passPoints[_passPoints.Count - 1];
        last.type = UnitPathPointType.Lean;
        _passPoints[_passPoints.Count - 1] = last;
    }

    public void RemoveLast()
    {
        _passPoints.RemoveAt(_passPoints.Count - 1);
    }

    public ReferencedPoint StartPosition
    {
        get { return start_position; }
    }

    public void SetStartPosition(ReferencedPoint position)
    {
        start_position = position;
        last_frame_id = position.Frame;
    }

    public UnitPathPoint AddPassPoint(
        ReferencedPoint position,
        UnitPathPointType type,
        LinkData link,
        Vector3 normal,
        BracedCoordinates braced_coordinates = default
    )
    {
        var pnt = new UnitPathPoint()
        {
            position = position,
            type = type,
            braced_coordinates = braced_coordinates,
            link = link,
            normal = normal
        };
        _passPoints.Add(pnt);
        last_frame_id = position.Frame;
        return pnt;
    }

    public UnitPathPoint AddPassPoint(
        Vector3 position,
        UnitPathPointType type,
        string area = null,
        BracedCoordinates braced_coordinates = default,
        Vector3 normal = default
    )
    {
        var pnt = new UnitPathPoint()
        {
            position = new ReferencedPoint(position, area),
            type = type,
            braced_coordinates = braced_coordinates,
            normal = normal
        };
        _passPoints.Add(pnt);
        last_frame_id = pnt.position.Frame;
        return pnt;
    }

    public UnitPathPoint AddPassPoint(
        ReferencedPoint position,
        UnitPathPointType type,
        BracedCoordinates braced_coordinates = default,
        Vector3 normal = default
    )
    {
        var pnt = new UnitPathPoint()
        {
            position = position,
            type = type,
            braced_coordinates = braced_coordinates,
            normal = normal
        };
        _passPoints.Add(pnt);
        last_frame_id = position.Frame;
        return pnt;
    }

    public int Count
    {
        get { return _passPoints.Count; }
    }

    MyList<UnitPathPoint> GetPassPoints()
    {
        return _passPoints;
    }

    public IEnumerator<UnitPathPoint> GetEnumerator()
    {
        return _passPoints.GetEnumerator();
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }

    public UnitPath()
    {
        _passPoints = new MyList<UnitPathPoint>();
    }

    public UnitPath(MyList<UnitPathPoint> passPoints)
    {
        _passPoints = passPoints;
    }

    // operator []
    public UnitPathPoint this[int index]
    {
        get { return _passPoints[index]; }
        set { _passPoints[index] = value; }
    }
}
