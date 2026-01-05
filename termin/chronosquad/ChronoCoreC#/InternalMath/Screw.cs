using UnityEngine;

public class Screw
{
    public Vector3 lin;
    public Vector3 ang;

    public Screw(Vector3 lin, Vector3 ang)
    {
        this.lin = lin;
        this.ang = ang;
    }

    public Screw(Screw other) : this(other.lin, other.ang) { }

    public override string ToString()
    {
        return string.Format("Screw({0}, {1})", lin, ang);
    }
}
