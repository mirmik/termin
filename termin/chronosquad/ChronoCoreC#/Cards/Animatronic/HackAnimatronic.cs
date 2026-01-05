// using System.Collections.Generic;
// using System;

// #if UNITY_64
// using UnityEngine;
// #endif

// public class HackAnimatronic : Animatronic
// {
// 	ReferencedPose _pose;
// 	IdleType _idle_type;

// 	public HackAnimatronic(
// 		long start_step,
// 		long finish_step,
// 		ReferencedPose pose,
// 		IdleType idle_type
// 	) : base(start_step, finish_step)
// 	{
// 		_idle_type = idle_type;
// 		_pose = pose;
// 	}

// 	public override bool IsLooped()
// 	{
// 		return true;
// 	}

// 	public HackAnimatronic() { }

// 	public override bool IsCroach(ITimeline tl)
// 	{
// 		return _idle_type == IdleType.Croach;
// 	}

// 	public override ReferencedPose GetReferencedPose(long stepstamp, ITimeline tl)
// 	{
// 		return _pose;
// 	}

// 	public Pose LocalPose()
// 	{
// 		return _pose.LocalPose();
// 	}

// 	public override AnimationType GetAnimationType(long local_step)
// 	{
// 		switch (_idle_type)
// 		{
// 			case IdleType.Stand:
// 				return AnimationType.Idle;
// 			case IdleType.Croach:
// 				return AnimationType.CroachIdle;
// 		}
// 		return AnimationType.Idle;
// 	}
// }
