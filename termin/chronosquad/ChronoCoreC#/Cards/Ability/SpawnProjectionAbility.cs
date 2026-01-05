#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class SpawnProjectionAbility : Ability
{
    public SpawnProjectionAbility() { }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target_position,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters
    )
    {
        Action act = () =>
        {
            var tlcopy = tl.Copy();
            var actor = last_used_stamp.Actor();
            var actor_tlcopy = tlcopy.GetActor(actor.ObjectId());
            var copy_actor_tlcopy = actor_tlcopy.SpawnCopyToPosition(target_position);
            Debug.Log("Name of spawn:" + copy_actor_tlcopy.Name());
            tlcopy.SetCurrentTimeline();
            tlcopy.AddObject(copy_actor_tlcopy);

            var promise_pose = new ReferencedPose(
                new Pose(target_position.LocalPosition, actor.Rotation()),
                target_position.Frame
            );

            long step = tlcopy.CurrentStep();
            (copy_actor_tlcopy as Actor).SetPromiseMark(promise_pose, step);

            tlcopy.GetChronoSphere().Select(copy_actor_tlcopy);
        };
        (tl as Timeline).AddAfterStepUpdateAction(act);
    }
}
