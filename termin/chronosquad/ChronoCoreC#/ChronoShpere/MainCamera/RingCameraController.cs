// using System.Collections;
// using System.Collections.Generic;
// using System;
// using System.Runtime.InteropServices;

// #if UNITY_64
// using UnityEngine.UI;
// using UnityEngine;
// #endif

// //#if UNITY_STANDALONE_WIN
// using System.Windows;


// public class RingCameraController : CameraController
// {
// 	// Camera _camera;
// 	public Transform _camera_linmover;
// 	public Transform _camera_rotator;
// 	// TimelineGraph time_line_graph = null;
// 	// CameraBounds _camera_bounds = null;

// 	// GameObject _automatic_target = null;
// 	// float yaw;
// 	// float pitch;

// 	//float rotation_sensitive = 0.1f;
// 	//float move_sensitive = 0.02f;
// 	//float roll_sensitive = 0.3f;
// 	Quaternion ring_quat = Quaternion.identity;
// 	// float rotate_mouse_sensitive = 5f;
// 	// float alt_rotation_sensitive = 0.2f;

// 	//bool is_right_mouse_button_pressed = false;
// 	// bool alt_pressed = false;
// 	// Vector3 alt_pressed_mouse_position;
// 	// Vector3 alt_pressed_world_position;
// 	// Vector3 alt_pressed_os_position;
// 	// Camera _main_camera;


// 	//bool right_pressed = false;
// 	//Vector3 right_pressed_mouse_position;
// 	Vector3 right_pressed_local_position;
// 	float right_start_camera_position_z;

// 	//public float minimal_camera_y = -50;
// 	//public float maximal_camera_y = 0;

// 	//Vector3 _camera_move_future = Vector3.zero;

// 	Pose camera_pose = new Pose(new Vector3(0, 10, 0), Quaternion.Euler(50, 0, 0));

// 	Quaternion ReferenceQuat()
// 	{
// 		return ReferenceObject.transform.rotation;
// 	}

// 	public override void TeleportToNewCenter(Vector3 pos, Vector3 up) {}

// 	protected override void Init()
// 	{
// 		yaw = transform.localRotation.eulerAngles.y;
// 		pitch = transform.localRotation.eulerAngles.x;
// 		pitch = 50;
// 		_main_camera = Camera.main;
// 		time_line_graph = GameObject.Find("TimelineGraphCamera")?.GetComponent<TimelineGraph>();

// 		InitCameraFromView();
// 		restore_orientation();

// 		SetTargetPosition(transform.localPosition);
// 	}

// 	void Start()
// 	{
// 		Init();
// 	}

// 	// Переместить камеру к новому центру. Используется для отображения персонажа при двойном клике на него
// 	// public void TeleportToNewCenter(Vector3 pos)
// 	// {
// 	// 	var current_direction = transform.forward;
// 	// 	var new_pos = pos - current_direction * 10;
// 	// 	target_position = new_pos;
// 	// 	transform.localPosition = new_pos;
// 	// }


// 	// public void ChangeCameraFrame(Transform frame)
// 	// {
// 	// 	_main_camera.transform.parent = frame;
// 	// }

// 	// public Transform CameraFrame()
// 	// {
// 	// 	return _main_camera.transform.parent;
// 	// }

// 	void InitCameraFromView()
// 	{
// 		camera_pose = new Pose(transform.localPosition, transform.rotation);
// 	}

// 	void RotateCameraWithCenter(Vector3 center, float angle)
// 	{
// 		// var camera_pos = transform.localPosition;
// 		// var diffpos = camera_pos - center;
// 		// var newpos = Quaternion.Euler(0, angle, 0) * diffpos;
// 		// SetTargetPosition(center + newpos);
// 		// var camera_rot = transform.rotation;
// 		// var newrot = Quaternion.Euler(0, angle, 0) * camera_rot;
// 		// transform.rotation = newrot;

// 		var up_basis = _camera_rotator.up;
// 		var right_basis = _camera_rotator.right;
// 		var forward_basis = _camera_rotator.forward;

// 		var right = Camera.main.transform.right;

// 		var f = Vector3.Dot(right, forward_basis);
// 		var t = Vector3.Dot(right, right_basis);

// 		f = f * angle*0.1f;
// 		t = t * angle*0.1f;

// 		var q = Quaternion.Euler(0, -angle*0.1f, 0);
// 		var newrot = q * Camera.main.transform.localRotation;
// 		Camera.main.transform.localRotation = newrot;

// 		// var main_camera_rot = Camera.main.transform.rotation;
// 		// var newrot = Quaternion.Euler(0, angle, 0) * main_camera_rot;
// 		// Camera.main.transform.rotation = newrot;

// 		ApplyDiff(t,f*0.5f);
// 	}

// 	// public void SaveAngles()
// 	// {
// 	// 	var camera_rot = this.transform.rotation;
// 	// 	var local_rot = _camera_rotator.transform.localRotation;
// 	// 	yaw = local_rot.eulerAngles.y;
// 	// 	pitch = local_rot.eulerAngles.x;
// 	// }

// 	public void CameraFutureMoveApply()
// 	{
// 		float coefficient = 7.0f;
// 		var pos = _camera_linmover.transform.localPosition;
// 		var applyed = _camera_move_future * Time.deltaTime * coefficient;
// 		var newpos = pos + applyed;
// 		SetTargetPosition(newpos);
// 		_camera_move_future -= applyed;
// 	}

// 	//Vector3 target_position = Vector3.zero;
// 	void SetTargetPosition(Vector3 pos)
// 	{
// 		if (_camera_bounds != null)
// 		{
// 			if (!_camera_bounds.IsValid(pos))
// 			{
// 				return;
// 			}
// 		}

// 		//transform.position = pos;
// 		target_position = pos;
// 	}

// 	void UpdateWithTargetPosition()
// 	{
// 		//transform.position += (target_position - transform.position) * 0.8f;
// 		_camera_linmover.transform.localPosition = target_position;
// 	}

// 	Matrix4x4 GetInverseProjectionMatrix()
// 	{
// 		Matrix4x4 mainProjectionMatrix =
// 			GL.GetGPUProjectionMatrix( _main_camera.projectionMatrix, false );
// 		return mainProjectionMatrix.inverse;
// 	}

// 	Matrix4x4 GetInverseViewMatrix()
// 	{
// 		Matrix4x4 mainViewMatrix = _main_camera.worldToCameraMatrix;
// 		return mainViewMatrix.inverse;
// 	}


// 		Quaternion CurrentRotQuat()
// 		{
// 			return ReferenceObject.transform.rotation * ring_quat;
// 		}

// 		Quaternion InvCurrentRotQuat()
// 		{
// 			return Quaternion.Inverse(CurrentRotQuat());
// 		}

// 		Quaternion InvReferenceQuat()
// 		{
// 			return Quaternion.Inverse(ReferenceQuat());
// 		}


// 	public override void LateUpdateImpl()
// 	{
// 		var obj = ReferenceObject.GetComponent<ObjectController>().GetObject();
// 		var scr = obj.GetReferencedVelocityScrew();
// 		//Debug.Log("ReferencedVelocityScrew = " + scr);

// 		_camera_rotator.transform.rotation = CurrentRotQuat();
// 		//Debug.Log("CurrentRotQuat = " + CurrentRotQuat());
// 		//_camera_rotator.transform.rotation = Quaternion.Euler(0, 0, Time.time * 16.0f);

// 		CameraFutureMoveApply();


// 		if (_automatic_target != null)
// 		{
// 			//CynematicCameraModeUpdate();
// 			return;
// 		}

// 		bool in_timeline_graph = time_line_graph != null && time_line_graph.IsCursorInViewport();

// 		if (Input.GetMouseButton(2)) {
// 			yaw += Input.GetAxis("Mouse X") * rotate_mouse_sensitive;
// 			pitch -= Input.GetAxis("Mouse Y") * rotate_mouse_sensitive;
// 			restore_orientation();
// 		}

// 		// if alt pressed
// 		if (Input.GetKey(KeyCode.LeftAlt))
// 		{
// 			if (alt_pressed == false)
// 			{
// 				Cursor.visible = false;
// 				alt_pressed_mouse_position = Input.mousePosition;
// 				alt_pressed_world_position =
// 					GameCore.camera_point_to_world_position(
// 						alt_pressed_mouse_position);

// 				POINT p;
// 				GetCursorPos(out p);
// 				alt_pressed_os_position = new Vector3(p.X, p.Y, 0);

// 				// disable mouse cursor
// 			}
// 			else
// 			{
// 				var mouse_position = Input.mousePosition;
// 				var diff = mouse_position - alt_pressed_mouse_position;
// 				var diff_x = diff.x;
// 				RotateCameraWithCenter(alt_pressed_world_position,
// 					diff_x * alt_rotation_sensitive);
// 				//SetCursorPos((int)alt_pressed_os_position.x, (int)alt_pressed_os_position.y);
// 				//SaveAngles();
// 			}
// 			alt_pressed = true;
// 		}
// 		else
// 		{
// 			Cursor.visible = true;
// 			alt_pressed = false;
// 		}

// 		// on mouse wheel
// 		if (Input.mouseScrollDelta.y != 0 && !in_timeline_graph)
// 			MouseScrollProcedure();

// 		// on mouse right button
// 		if (Input.GetMouseButton(1)  && !in_timeline_graph)
// 		{
// 			if (right_pressed == false)
// 			{
// 				right_pressed_mouse_position = Input.mousePosition;


// 				right_pressed_local_position =
// 					InvReferenceQuat() *
// 						(GameCore.camera_point_to_world_position(
// 							right_pressed_mouse_position));
// 				right_start_camera_position_z = _camera_linmover.transform.localPosition.z;
// 			}
// 			else
// 			{


// 				var mouse_position = Input.mousePosition;
// 				var global_right_pressed_world_position =
// 					ReferenceQuat() * (right_pressed_local_position);

// 				Plane plane = new Plane(_camera_rotator.up, global_right_pressed_world_position);
// 				Ray ray = _main_camera.ScreenPointToRay(mouse_position);
// 				float enter;
// 				plane.Raycast(ray, out enter);
// 				var world_position = ray.GetPoint(enter);

// 				//var world_position =
// 				//	);



// 				var diff = global_right_pressed_world_position - world_position;
// 				var diff_in_rot_space = InvCurrentRotQuat() * diff;
// 				var diff_z = diff_in_rot_space.z;

// 				var diff_x = diff_in_rot_space.x;
// 				var wyx = new Vector2(world_position.y, world_position.x);
// 				var radius = wyx.magnitude;
// 				var angle_diff_x = diff_x / radius * 180 / Mathf.PI;

// 				ApplyDiff(angle_diff_x, diff_z);
// 			}
// 			right_pressed = true;
// 		}
// 		else
// 		{
// 			right_pressed = false;
// 		}

// 		UpdateWithTargetPosition();


// 		var inverseProjectionMatrix = GetInverseProjectionMatrix();
// 		var inverseViewMatrix = GetInverseViewMatrix();
// 		Shader.SetGlobalMatrix("InverseViewMatrix", inverseViewMatrix);
// 		Shader.SetGlobalMatrix("InverseProjectionMatrix", inverseProjectionMatrix);
// 	}


// 	void ApplyDiff(float angle_diff_x, float diff_z)
// 	{
// 		bool shift_pressed = Input.GetKey(KeyCode.LeftShift);

// 		if (!shift_pressed)
// 		{
// 			float coeff = 0.7f;
// 			angle_diff_x *= coeff;
// 			diff_z *= coeff;
// 			var rdiff = Quaternion.Euler(0, 0, angle_diff_x * 0.5f);
// 			ring_quat = rdiff * ring_quat;
// 			ring_quat = ring_quat.normalized;
// 			_camera_rotator.transform.rotation =
// 				CurrentRotQuat();
// 		}
// 		else
// 		{
// 			target_position.x += angle_diff_x;
// 		}


// 		right_start_camera_position_z += diff_z;
// 		float MaxZ = 45;
// 		if (right_start_camera_position_z < -MaxZ)
// 		{
// 			right_start_camera_position_z = -MaxZ;
// 		}
// 		else if (right_start_camera_position_z > MaxZ)
// 		{
// 			right_start_camera_position_z = MaxZ;
// 		};
// 		target_position.z = right_start_camera_position_z;
// 	}


// 	void MouseScrollProcedure()
// 	{
// 		if (UsedActionBuffer.Instance.UsedAction != null)
// 		{
// 			bool prevent = UsedActionBuffer.Instance.UsedAction.MouseScrollInterrupt();
// 			if (prevent)
// 				return;
// 		}

// 		if (!Input.GetKey(KeyCode.LeftControl)) {
// 			if (Input.GetKey(KeyCode.LeftShift) )
// 			{
// 				GameCore.on_mouse_wheel_time_control(Input.mouseScrollDelta.y);
// 			}
// 			else {
// 				var camera_pos = transform.localPosition;
// 				var direction_of_camera =
// 					_camera_rotator.transform.InverseTransformDirection(_main_camera.transform.forward);
// 				var y = camera_pos.y;

// 				if (Input.mouseScrollDelta.y > 0)
// 				{
// 					y -= 1;
// 				}
// 				else
// 				{
// 					y += 1;
// 				}

// 				if (y < minimal_camera_y)
// 				{
// 					y = minimal_camera_y;
// 				}
// 				else if (y > maximal_camera_y)
// 				{
// 					y = maximal_camera_y;
// 				}

// 				var ydiff = camera_pos.y - y;
// 				var direction_y_proj = direction_of_camera.y;
// 				var ndir_xz = (direction_of_camera / direction_y_proj) * ydiff;
// 				ndir_xz.x = 0;

// 				_camera_move_future -= ndir_xz;
// 			}
// 		}
// 	}

// 	//public ControlableActor last_selected_actor = null;
// 	//public PlatformView last_frame = null;
// 	// public void CheckCameraFrameAutomatic()
// 	// {
// 	// 	var selected_actor = GameCore.SelectedActor();
// 	// 	if (selected_actor == null)
// 	// 	{
// 	// 		last_selected_actor = null;
// 	// 		last_frame = null;
// 	// 		return;
// 	// 	}

// 	// 	var frame_name = selected_actor.MovedWithFrame();
// 	// 	var frame = GameCore.FindPlatform(frame_name.name);

// 	// 	if (selected_actor != last_selected_actor)
// 	// 	{
// 	// 		Debug.Log("Selected actor changed" + selected_actor.name);
// 	// 		last_selected_actor = selected_actor;
// 	// 		last_frame = frame;
// 	// 	}
// 	// 	else
// 	// 	{
// 	// 		if (last_frame != frame)
// 	// 		{
// 	// 			Debug.Log("Selected actor frame changed" + selected_actor.name);
// 	// 			if (frame != null)
// 	// 			{
// 	// 				ChangeCameraFrame(frame.transform);
// 	// 			}
// 	// 		}
// 	// 	}
// 	// }


// 	// void CynematicCameraModeUpdate()
// 	// {
// 	// 	Quaternion rotation = Quaternion.LookRotation(_automatic_target.transform.position - transform.position);
// 	// 	this.transform.rotation = rotation;


// 	// 	if (Input.GetMouseButton(2)) {
// 	// 		float x = -Input.GetAxis("Mouse X");
// 	// 		float y = -Input.GetAxis("Mouse Y");

// 	// 		Vector3 right = transform.right;
// 	// 		Vector3 up = transform.up;

// 	// 		transform.position += right * x * 0.3f;
// 	// 		transform.position += up * y * 0.3f;

// 	// 		Quaternion rotation_ = Quaternion.LookRotation(_automatic_target.transform.position - transform.position);
// 	// 		this.transform.rotation = rotation_;
// 	// 	}


// 	// 	SaveAngles();
// 	// }


// 	// public void move_forward(float sens)
// 	// {
// 	// 	transform.position += transform.forward * sens;
// 	// }

// 	// public void move_backward(float sens)
// 	// {
// 	// 	transform.position += transform.forward * sens;
// 	// }

// 	void restore_orientation()
// 	{
// 		transform.localRotation = Quaternion.Euler(pitch, yaw, 0);
// 	}

// 	// public Vector3 get_position()
// 	// {
// 	// 	return transform.position;
// 	// }

// 	// public void set_position(Vector3 pos)
// 	// {
// 	// 	transform.position = pos;
// 	// }


// 	public void CenterOn(Vector3 pos)
// 	{
// 		var camera_pos = this.transform.localPosition;
// 		var direction_of_camera = _main_camera.transform.forward;
// 		var ydiff = Math.Abs(camera_pos.y - pos.y);
// 		var ndir_xz = direction_of_camera  * ydiff;

// 		var new_pos = new Vector3(
// 			pos.x - ndir_xz.x, camera_pos.y, pos.z - ndir_xz.z);

// 		this.transform.localPosition = new_pos;
// 	}

// 	public void AutomaticTargetObject(GameObject obj)
// 	{
// 		_automatic_target = obj;
// 	}

// 	public void DisableAutomaticTargeting()
// 	{
// 		_automatic_target = null;
// 	}
// }
