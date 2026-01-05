using UnityEngine;

// Устанавливается на блок. Прилегание осуществляется к forward стороне блока.

public enum CornerLeanZoneType
{
    None,
    Left,
    Right
}

public class CornerLeanZone : MonoBehaviour
{
    public CornerLeanZoneType Type = CornerLeanZoneType.Right;

    public BracedCoordinates GetBracedCoordinates()
    {
        var bracedCoordinates = new BracedCoordinates();

        bracedCoordinates.Rotation = Quaternion.LookRotation(transform.forward, transform.up);
        bracedCoordinates.TopPosition = transform.TransformPoint(new Vector3(0, -0.5f, 0.5f));
        bracedCoordinates.CornerLean = Type;

        return bracedCoordinates;
    }
}
