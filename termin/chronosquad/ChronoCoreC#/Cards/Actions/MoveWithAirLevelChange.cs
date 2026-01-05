// using UnityEngine;
// using System;
// using System.Collections;

// public class MoveWithAirLevelChange : MonoBehaviourAction
// {
// 	Type ability_type;
// 	DroneController drone;
// 	KeyCode keycode = KeyCode.A;

// 	public override string TooltipText()
// 	{
// 		return "Перемещение с возможностью изменения высоты";
// 	}

// 	public Ability GetAbility()
// 	{
// 		if (ability_type == null)
// 			Debug.LogError("Ability type is not set: " + this);
// 		var obj = _actor.GetObject();
// 		return obj.AbilityList.GetAbility(ability_type);
// 	}

// 	public sealed override float CooldownTime()
// 	{
// 		return 0.0f;
// 	}

// 	public sealed override float GetFillPercent()
// 	{
// 		return 100.0f;
// 	}

// 	public  override void Init()
// 	{
// 		drone = this.GetComponent<DroneController>();
// 		_actor = this.GetComponent<ObjectController>();
// 		var activity = new Activity(icon, this, keycode);
// 		_actor.add_activity(activity);
// 		setup_renderer();
// 		base.Init();
// 	}

// 	public override void OnIconClick()
// 	{
// 		_line_renderer.enabled = true;
// 		UsedActionBuffer.Instance.SetUsedAction(this);
// 	}

// 	public override void Cancel ()
// 	{
// 		UsedActionBuffer.Instance.SetUsedAction(null);
// 		_line_renderer.enabled = false;
// 		ClearEffects();
// 	}

// 	public override void OnEnvironmentClick(ClickInformation click)
// 	{
// 		drone.GetComponent<ControlableActor>().on_air_click(
// 			click.environment_hit.point, false, null
// 		);
// 	}

// 	public override void OnActorClick(GameObject actor, ClickInformation click)
// 	{
// 		throw new NotImplementedException();
// 	}


// 	public override void UpdateActive()
// 	{
// 			_line_renderer.startWidth = LineWidth;
// 			_line_renderer.endWidth = LineWidth;


// 			Vector3 start_position = this.transform.position + new Vector3(0, 1, 0);
// 			Vector3 mouse_pos = Input.mousePosition;

// 			var hit = GameCore.CursorEnvironmentHit(mouse_pos);

// 			if (hit.collider != null)
// 			{
// 				Vector3 world_pos = hit.point;
// 				_line_renderer.positionCount = 2;
// 				var curpos = this.transform.position;

// 				_line_renderer.SetPosition(0, curpos);
// 				_line_renderer.SetPosition(1, world_pos + new Vector3(
// 					0, drone.AirLevel, 0));
// 			}
// 			else
// 			{
// 				_line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
// 			}
// 		}

// 	public override global::System.Boolean MouseScrollInterrupt()
// 	{
// 		var mouse_diff = Input.mouseScrollDelta.y;

// 		drone.AirLevelTarget += mouse_diff * 0.2f;

// 		return true;
// 	}

// }
