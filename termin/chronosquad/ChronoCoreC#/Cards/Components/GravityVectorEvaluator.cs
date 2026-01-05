using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public abstract class PseudoGravityVectorEvaluator : ItemComponent
{
    public PseudoGravityVectorEvaluator(ObjectOfTimeline owner) : base(owner) { }

    public override void Start()
    {
        Owner.pseudoGravityVectorEvaluator = this;
    }

    abstract public Vector3 Evaluate(Vector3 global_point);
}

public class RingPseudoGravityEvaluator : PseudoGravityVectorEvaluator
{
    public RingPseudoGravityEvaluator(ObjectOfTimeline owner) : base(owner) { }

    public override ItemComponent Copy(ObjectOfTimeline owner)
    {
        return new RingPseudoGravityEvaluator(owner);
    }

    public override Vector3 Evaluate(Vector3 global_point)
    {
        Debug.Log("RingPseudoGravityEvaluator.Execute");
        var c = global_point;
        return new Vector3(-c.x, -c.y, 0);
    }
}
