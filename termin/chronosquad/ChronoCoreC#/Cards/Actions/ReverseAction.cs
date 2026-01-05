// using System.Collections;
// using System.Collections.Generic;
// using UnityEngine;

// public class ReverseAction : TargetChooseAction
// {
// 	ReverseAction() : base(KeyCode.N) { }

// 	protected override void ActionTo(GameObject actor)
// 	{
// 		long step = GameCore.Chronosphere().current_timeline().CurrentStep();
// 		GuardView view = actor.GetComponent<GuardView>();
// 		Actor guard = view.guard() as Actor;
// 		guard.reverse(step);
// 	}

// 	public override string TooltipText()
// 	{
// 		return "Реверсия времени противника";
// 	}
// }
