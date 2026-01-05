using System.Collections;
using System.Collections.Generic;
using System;
using System.Runtime.InteropServices;

#if UNITY_64
using UnityEngine.UI;
using UnityEngine;
#endif

//#if UNITY_STANDALONE_WIN
using System.Windows;

[StructLayout(LayoutKind.Sequential)]
public struct POINT
{
    public int X;
    public int Y;
}

//#endif

public enum CynematicFrameMode
{
    RelativePositionOnly,
    Relative,
    Absolute
}

public interface ICameraBounds
{
    bool IsValid(Vector3 pos);
}

public class CameraController : AbstractCameraController
{
    public GameObject ReferenceObject;
    protected Camera _camera;
    protected TimelineGraph time_line_graph = null;
    protected CameraBounds _camera_bounds = null;

    protected GameObject _automatic_target = null;
    protected float yaw;
    protected float pitch;

    //float rotation_sensitive = 0.1f;
    //float move_sensitive = 0.02f;
    //float roll_sensitive = 0.3f;
    protected float rotate_mouse_sensitive = 5f;
    protected float alt_rotation_sensitive = 0.2f;

    //bool is_right_mouse_button_pressed = false;
    protected bool alt_pressed = false;
    protected Vector3 alt_pressed_mouse_position;
    protected Vector3 alt_pressed_world_position;
    protected Vector3 alt_pressed_os_position;
    protected Camera _main_camera;

    protected bool right_pressed = false;
    protected Vector3 right_pressed_mouse_position;
    protected Vector3 right_pressed_world_position;
    protected Vector3 right_start_camera_position;

    public float minimal_camera_y = 2;
    public float maximal_camera_y = 100;

    protected Vector3 _camera_move_future = Vector3.zero;

    //ReferencedPose camera_pose = new ReferencedPose(
    //		new Pose(new Vector3(0, 10, 0), Quaternion.Euler(0, 0, 0)), null);

    protected Pose camera_pose = new Pose(new Vector3(0, 10, 0), Quaternion.Euler(50, 0, 0));

    public override ObjectId ReferenceObjectId()
    {
        if (ReferenceObject == null)
        {
            return default(ObjectId);
        }
        return ReferenceObject.GetComponent<ObjectController>().GetObject().ObjectId();
    }

    // // cynematic section
    // MyList<GameObject> cynematic_targets;
    // MyList<float> cynematic_targets_priority;


    // public GameObject CynematicFrameBase {set; get;}
    // public CynematicFrameMode CynematicFrameMode {set; get;} = CynematicFrameMode.RelativePositionOnly;
    // public ComplexEaseFrame EaseFrames {set; get;} = new ComplexEaseFrame();

    // Pose FrameFromCurves(float time)
    // {
    // 	return EaseFrames.Evaluate(time);
    // }

    // Pose CynematicCameraFrame()
    // {
    // 	var time = _chronosphere_controller.CurrentTimelineFlowTime();
    // 	var evaluate_frame = FrameFromCurves(time);

    // 	switch (CynematicFrameMode)
    // 	{
    // 		case CynematicFrameMode.RelativePositionOnly:
    // 			return new Pose(evaluate_frame.position + CynematicFrameBase.position, evaluate_frame.rotation);
    // 		case CynematicFrameMode.Relative:
    // 			return CynematicFrameBase * evaluate_frame;
    // 		case CynematicFrameMode.Absolute:
    // 			return evaluate_frame;
    // 	}
    // }

    // Vector3 CynematicTargetPosition()
    // {
    // 	Vector3 accumulator = Vector3.zero;
    // 	float priority_accumulator = 0;
    // 	for (int i = 0; i < cynematic_targets.Count; i++)
    // 	{
    // 		var target = cynematic_targets[i];
    // 		var priority = cynematic_targets_priority[i];
    // 		accumulator += target.transform.position * priority;
    // 		priority_accumulator += priority;
    // 	}
    // 	return accumulator / priority_accumulator;
    // }

    // void CynematicCameraRelativeModeUpdate()
    // {
    // 	var frame = CynematicCameraFrame();
    // 	var target_position = CynematicTargetPosition();
    // 	var camera_pos = frame.position;
    // 	var rotation = Quaternion.LookRotation(target_position - camera_pos, frame.rotation * Vector3.up);
    // 	transform.position = camera_pos;
    // 	transform.rotation = rotation;
    // }

    void Awake()
    {
        _instance = this;
        _camera = GetComponent<Camera>();
        _camera_bounds = transform.Find("CameraBounds")?.GetComponent<CameraBounds>();
    }

    protected virtual void Init()
    {
        yaw = transform.rotation.eulerAngles.y;
        pitch = transform.rotation.eulerAngles.x;
        pitch = 50;
        _main_camera = Camera.main;
        time_line_graph = GameObject.Find("TimelineGraphCamera")?.GetComponent<TimelineGraph>();

        InitCameraFromView();
        restore_orientation();

        SetTargetPosition(transform.position);
    }

    void Start()
    {
        Init();
    }

    // Переместить камеру к новому центру. Используется для отображения персонажа при двойном клике на него
    public override void TeleportToNewCenter(Vector3 pos, Vector3 up)
    {
        var current_direction = transform.forward;
        var new_pos = pos - current_direction * 10;
        target_position = new_pos;
        transform.position = new_pos;
    }

    public override void ChangeCameraFrame(Transform frame)
    {
        _main_camera.transform.parent = frame;
    }

    public Transform CameraFrame()
    {
        return _main_camera.transform.parent;
    }

    void InitCameraFromView()
    {
        camera_pose = new Pose(transform.position, transform.rotation);
    }

    void RotateCameraWithCenter(Vector3 center, float angle)
    {
        var camera_pos = transform.position;
        var diffpos = camera_pos - center;
        var newpos = Quaternion.Euler(0, angle, 0) * diffpos;
        SetTargetPosition(center + newpos);
        var camera_rot = transform.rotation;
        var newrot = Quaternion.Euler(0, angle, 0) * camera_rot;
        transform.rotation = newrot;
    }

    public void SaveAngles()
    {
        var camera_rot = this.transform.rotation;
        yaw = camera_rot.eulerAngles.y;
        pitch = camera_rot.eulerAngles.x;
    }

    public void CameraFutureMoveApply()
    {
        float coefficient = 7.0f;
        var pos = transform.position;
        var applyed = _camera_move_future * Time.deltaTime * coefficient;
        var newpos = pos + applyed;
        SetTargetPosition(newpos);
        _camera_move_future -= applyed;
    }

    protected Vector3 target_position = Vector3.zero;

    void SetTargetPosition(Vector3 pos)
    {
        if (_camera_bounds != null)
        {
            if (!_camera_bounds.IsValid(pos))
            {
                return;
            }
        }

        //transform.position = pos;
        target_position = pos;
    }

    void UpdateWithTargetPosition()
    {
        //transform.position += (target_position - transform.position) * 0.8f;
        transform.position = target_position;
    }

    // void LateUpdate()
    // {
    // 	LateUpdateImpl();
    // }

    public override void LateUpdateImpl()
    {
        CameraFutureMoveApply();

        if (_automatic_target != null)
        {
            //CynematicCameraModeUpdate();
            return;
        }

        bool in_timeline_graph = time_line_graph != null && time_line_graph.IsCursorInViewport();

        if (Input.GetMouseButton(2))
        {
            yaw += Input.GetAxis("Mouse X") * rotate_mouse_sensitive;
            pitch -= Input.GetAxis("Mouse Y") * rotate_mouse_sensitive;
            restore_orientation();
        }

        // if alt pressed
        if (Input.GetKey(KeyCode.LeftAlt))
        {
            if (alt_pressed == false)
            {
                Cursor.visible = false;
                alt_pressed_mouse_position = Input.mousePosition;
                alt_pressed_world_position = GameCore.camera_point_to_world_position(
                    alt_pressed_mouse_position
                );

                POINT p;
                GetCursorPos(out p);
                alt_pressed_os_position = new Vector3(p.X, p.Y, 0);

                // disable mouse cursor
            }
            else
            {
                var mouse_position = Input.mousePosition;
                var diff = mouse_position - alt_pressed_mouse_position;
                var diff_x = diff.x;
                RotateCameraWithCenter(alt_pressed_world_position, diff_x * alt_rotation_sensitive);
                SetCursorPos((int)alt_pressed_os_position.x, (int)alt_pressed_os_position.y);
                SaveAngles();
            }
            alt_pressed = true;
        }
        else
        {
            Cursor.visible = true;
            alt_pressed = false;
        }

        // on mouse wheel
        if (Input.mouseScrollDelta.y != 0 && !in_timeline_graph)
            MouseScrollProcedure();

        // on mouse right button
        if (Input.GetMouseButton(1) && !in_timeline_graph)
        {
            if (right_pressed == false)
            {
                right_pressed_mouse_position = Input.mousePosition;
                try
                {
                    right_pressed_world_position = GameCore.camera_point_to_world_position(
                        right_pressed_mouse_position
                    );
                }
                catch
                {
                    return;
                }
                right_start_camera_position = transform.position;
            }
            else
            {
                var mouse_position = Input.mousePosition;

                Plane plane = new Plane(Vector3.up, right_pressed_world_position);
                float enter = 0.0f;
                Ray ray = _main_camera.ScreenPointToRay(mouse_position);
                if (!plane.Raycast(ray, out enter))
                {
                    Debug.Log("ScreenPointToRay fault");
                    return;
                }
                var world_position = ray.GetPoint(enter);
                world_position.y = right_pressed_world_position.y;

                var diff = right_pressed_world_position - world_position;
                var diff_x = diff.x;
                var diff_z = diff.z;

                var new_camera_position = right_start_camera_position;
                new_camera_position.x += diff_x;
                new_camera_position.z += diff_z;

                SetTargetPosition(new_camera_position);
                right_start_camera_position = new_camera_position;
            }
            right_pressed = true;
        }
        else
        {
            right_pressed = false;
        }

        UpdateWithTargetPosition();

        var inverseProjectionMatrix = GetInverseProjectionMatrix();
        var inverseViewMatrix = GetInverseViewMatrix();
        Shader.SetGlobalMatrix("InverseViewMatrix", inverseViewMatrix);
        Shader.SetGlobalMatrix("InverseProjectionMatrix", inverseProjectionMatrix);
    }

    void MouseScrollProcedure()
    {
        if (UsedActionBuffer.Instance.UsedAction != null)
        {
            bool prevent = UsedActionBuffer.Instance.UsedAction.MouseScrollInterrupt();
            if (prevent)
                return;
        }

        if (!Input.GetKey(KeyCode.LeftControl))
        {
            if (Input.GetKey(KeyCode.LeftShift))
            {
                GameCore.on_mouse_wheel_time_control(Input.mouseScrollDelta.y);
            }
            else
            {
                var camera_pos = transform.position;
                var direction_of_camera = _main_camera.transform.forward;
                var y = camera_pos.y;

                if (Input.mouseScrollDelta.y > 0)
                {
                    y -= 1;
                }
                else
                {
                    y += 1;
                }

                if (y < minimal_camera_y)
                {
                    y = minimal_camera_y;
                }
                else if (y > maximal_camera_y)
                {
                    y = maximal_camera_y;
                }

                var ydiff = camera_pos.y - y;
                var direction_y_proj = direction_of_camera.y;
                var ndir_xz = (direction_of_camera / direction_y_proj) * ydiff;

                _camera_move_future -= ndir_xz;
            }
        }
    }

    public ControlableActor last_selected_actor = null;
    public PlatformView last_frame = null;

    public override void move_forward(float sens)
    {
        transform.position += transform.forward * sens;
    }

    public void move_backward(float sens)
    {
        transform.position += transform.forward * sens;
    }

    void restore_orientation()
    {
        transform.rotation = Quaternion.Euler(pitch, yaw, 0);
    }

    public Vector3 get_position()
    {
        return transform.position;
    }

    public void set_position(Vector3 pos)
    {
        transform.position = pos;
    }

    public void CenterOn(Vector3 pos)
    {
        var camera_pos = this.transform.position;
        var direction_of_camera = _main_camera.transform.forward;
        var ydiff = Math.Abs(camera_pos.y - pos.y);
        var ndir_xz = direction_of_camera * ydiff;

        var new_pos = new Vector3(pos.x - ndir_xz.x, camera_pos.y, pos.z - ndir_xz.z);

        this.transform.position = new_pos;
    }

    public void AutomaticTargetObject(GameObject obj)
    {
        _automatic_target = obj;
    }

    public void DisableAutomaticTargeting()
    {
        _automatic_target = null;
    }
}
