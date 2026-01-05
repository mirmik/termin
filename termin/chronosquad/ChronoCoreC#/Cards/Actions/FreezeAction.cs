// using System.Collections;
// using System.Collections.Generic;
// using UnityEngine;

// public class FreezeAction : MonoBehaviourAction
// {
// 	public Material material;
// 	public Texture2D _icon;

// 	bool _gun_clicked = false;

// 	public string TooltipText()
// 	{
// 		return "Остановить время противника";
// 	}

// 	public void OnIconClick()
// 	{
// 		_gun_clicked = true;
// 		_line_renderer.enabled = true;
// 		UsedActionBuffer.Instance.SetUsedAction(this);
// 	}

// 	public void Cancel()
// 	{
// 		UsedActionBuffer.Instance.SetUsedAction(null);
// 		_gun_clicked = false;
// 		_line_renderer.enabled = false;
// 	}

// 	void Freeze(GameObject actor)
// 	{
// 		long step = GameCore.Chronosphere().current_timeline().CurrentStep();
// 		GuardView view = actor.GetComponent<GuardView>();
// 		Actor guard = view.guard() as Actor;
// 		guard.freeze(step);
// 	}

// 	void Update()
// 	{
// 		if (_gun_clicked)
// 		{
// 			_line_renderer.startWidth = LineWidth;
// 			_line_renderer.endWidth = LineWidth;
// 			_line_renderer.SetPosition(0, this.transform.position + new Vector3(0, 1, 0));

// 			Vector3 mouse_pos = Input.mousePosition;

// 			RaycastHit hit;
// 			Ray ray = Camera.main.ScreenPointToRay(mouse_pos);
// 			if (Physics.Raycast(ray, out hit))
// 			{
// 				Vector3 world_pos = hit.point;
// 				_line_renderer.SetPosition(1, world_pos);
// 			}
// 			else
// 			{
// 				_line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
// 			}
// 		}
// 	}

// 	public void OnEnvironmentClick(ClickInformation click)
// 	{
// 		Cancel();
// 	}

// 	public void OnActorClick(GameObject actor, ClickInformation click)
// 	{
// 		if (actor == this.gameObject)
// 		{
// 			Cancel();
// 			return true;
// 		}

// 		//Debug.Log("GunAction.OnActorClick: SHOOT");
// 		Freeze(actor);
// 		Cancel();
// 		return true;
// 	}
// }
