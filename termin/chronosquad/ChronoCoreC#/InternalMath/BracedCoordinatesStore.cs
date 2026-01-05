using UnityEngine;
using Unity.AI.Navigation;

public class UpDownBracedCoordinateGenerator : MonoBehaviour
{
    public GameObject Reference;
    public NavMeshLink link;
    public Vector3 EdgePositionInLinkFrame;

    public BracedCoordinates NonRefGenerateBracedCoordinates()
    {
        var apoint = link.transform.TransformPoint(link.startPoint);
        var bpoint = link.transform.TransformPoint(link.endPoint);
        var cpoint = link.transform.TransformPoint(EdgePositionInLinkFrame);
        var rotation = link.transform.rotation;

        var a = apoint;
        var b = bpoint;
        var c = cpoint;

        var up = rotation * Vector3.up;
        var back = rotation * Vector3.back;
        var back_rotation = Quaternion.LookRotation(back, up);

        ReferencedPose toppose = new ReferencedPose(a, rotation, default(ObjectId));
        ReferencedPose botpose = new ReferencedPose(b, rotation, default(ObjectId));
        ReferencedPose edgepose = new ReferencedPose(c, back_rotation, default(ObjectId));
        ReferencedPose back_toppose = new ReferencedPose(a, back_rotation, default(ObjectId));
        ReferencedPose back_botpose = new ReferencedPose(b, back_rotation, default(ObjectId));

        var bc = new BracedCoordinates();
        bc.APose = toppose;
        bc.BPose = botpose;
        bc.CPose = edgepose;
        bc.DPose = back_toppose;
        bc.EPose = back_botpose;
        return bc;
    }

    public BracedCoordinates GenerateBracedCoordinates()
    {
        if (Reference == null)
            return NonRefGenerateBracedCoordinates();

        var apoint = link.transform.TransformPoint(link.startPoint);
        var bpoint = link.transform.TransformPoint(link.endPoint);
        var cpoint = link.transform.TransformPoint(EdgePositionInLinkFrame);

        var a = Reference.transform.InverseTransformPoint(apoint);
        var b = Reference.transform.InverseTransformPoint(bpoint);
        var c = Reference.transform.InverseTransformPoint(cpoint);

        var rotation = Quaternion.Inverse(Reference.transform.rotation) * link.transform.rotation;

        var up = rotation * Vector3.up;
        var back = rotation * Vector3.back;
        var back_rotation = Quaternion.LookRotation(back, up);

        ReferencedPose toppose = new ReferencedPose(a, rotation, new ObjectId(Reference.name));
        ReferencedPose botpose = new ReferencedPose(b, rotation, new ObjectId(Reference.name));
        ReferencedPose edgepose = new ReferencedPose(
            c,
            back_rotation,
            new ObjectId(Reference.name)
        );
        ReferencedPose back_toppose = new ReferencedPose(
            a,
            back_rotation,
            new ObjectId(Reference.name)
        );
        ReferencedPose back_botpose = new ReferencedPose(
            b,
            back_rotation,
            new ObjectId(Reference.name)
        );

        var bc = new BracedCoordinates();
        bc.APose = toppose;
        bc.BPose = botpose;
        bc.CPose = edgepose;
        bc.DPose = back_toppose;
        bc.EPose = back_botpose;
        return bc;
    }

    public Vector3 EdgeGlobalPosition()
    {
        return link.transform.TransformPoint(EdgePositionInLinkFrame);
    }
}
