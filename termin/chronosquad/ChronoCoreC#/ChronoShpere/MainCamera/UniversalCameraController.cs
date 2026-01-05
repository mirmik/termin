using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public abstract class NavigateModule
{
    protected float TimeConstant = 0.1f;

    public abstract void RestoreCameraPose(UniversalCameraController cc);

    public abstract void ReInitFromCameraPose(UniversalCameraController cc);

    public virtual void ApplyScroll(UniversalCameraController cc, float signal)
    {
        cc.pose_in_reference_frame.position += cc.pose_in_reference_frame.Forward() * signal;
    }

    public abstract void TeleportToNewCenter(Vector3 pos, Vector3 up);

    public virtual void ApplyAltRotation(
        UniversalCameraController cc,
        float signal,
        float signal2
    ) { }

    // public virtual void RotateCamera(UniversalCameraController cc, float x, float y)
    // {
    // 	var xq = Quaternion.Euler(0, x, 0);
    // 	var yq = Quaternion.Euler(y, 0, 0);
    // 	var currotation = cc.pose_in_reference_frame.rotation;
    // 	var newrotation = currotation * xq * yq;
    // 	newrotation.SetLookRotation(
    // 		newrotation * Vector3.forward,
    // 		Vector3.up);
    // 	cc.pose_in_reference_frame.rotation = newrotation;
    // }

    // protected Vector3 CorrectGlobalTouchPosition(
    // 	UniversalCameraController cc, Vector3 global_position)
    // {
    // 	var diff = global_position -
    // 		Camera.main.transform.position;
    // 	var dist = diff.magnitude;
    // 	if (dist > MaxTouchDist)
    // 	{
    // 		dist = MaxTouchDist;
    // 		global_position =
    // 			Camera.main.transform.position + diff.normalized * dist;
    // 	}
    // 	return global_position;
    // }

    public Plane NavigationPlane(UniversalCameraController cc, Vector3 normal_vector)
    {
        var mouse_position = Input.mousePosition;
        var plane_over_global_right_pressed = new Plane(normal_vector, cc.TouchWorldPosition());
        return plane_over_global_right_pressed;
    }

    public virtual void ApplyRightMove(UniversalCameraController cc)
    {
        bool is_shift_pressed = Input.GetKey(KeyCode.LeftShift);
        var normal_vector = is_shift_pressed
            ? cc.PoseOfReferenceFrame().Forward()
            : cc.PoseOfReferenceFrame().Up();

        var plane_over_global_right_pressed = NavigationPlane(cc, normal_vector);
        var ray = Camera.main.ScreenPointToRay(Input.mousePosition);

        float enter;
        if (plane_over_global_right_pressed.Raycast(ray, out enter))
        {
            var hit_point = ray.GetPoint(enter);
            var hit_point_in_reference_frame = cc.PositionInReferencedFrame(hit_point);
            var delta = hit_point_in_reference_frame - cc.touch_position_in_reference_frame;

            cc.pose_in_reference_frame.position -= (delta * (Time.deltaTime / TimeConstant));
        }
    }

    public virtual void ApplyWheelMove(UniversalCameraController cc)
    {
        var normal_vector = -Camera.main.transform.forward;

        var plane_over_global_wheel_pressed = NavigationPlane(cc, normal_vector);
        var ray = Camera.main.ScreenPointToRay(Input.mousePosition);

        float enter;
        if (plane_over_global_wheel_pressed.Raycast(ray, out enter))
        {
            var hit_point = ray.GetPoint(enter);
            var hit_point_in_reference_frame = cc.PositionInReferencedFrame(hit_point);
            var delta = hit_point_in_reference_frame - cc.touch_position_in_reference_frame;

            var delta_in_global_frame = cc.PoseOfReferenceFrame().TransformDirection(delta);
            var delta_in_camera_frame = Camera.main.transform.InverseTransformDirection(
                delta_in_global_frame
            );

            var x = delta_in_camera_frame.x;
            var y = delta_in_camera_frame.y;

            var rad = (hit_point - Camera.main.transform.position).magnitude;

            var xangle = x / rad;
            var yangle = y / rad;

            var sens = 20.0f;
            var currotation = cc.pose_in_reference_frame.rotation;
            var euler = currotation.eulerAngles;
            var yaw = euler.y;
            var pitch = euler.x > 180.0f ? euler.x - 360.0f : euler.x;

            Debug.Log("Yaw: " + yaw + " Pitch: " + pitch);

            pitch = Mathf.Clamp(pitch, -75, 75);

            yaw -= xangle * sens;
            pitch += yangle * sens;

            var newrotation = Quaternion.Euler(pitch, yaw, 0);
            cc.pose_in_reference_frame.rotation = newrotation;
        }
    }
}

public class HorizonNavigateModule : NavigateModule
{
    Pose body_frame = Pose.Identity;

    public override void RestoreCameraPose(UniversalCameraController cc)
    {
        cc.pose_in_reference_frame = body_frame;
    }

    public override void ReInitFromCameraPose(UniversalCameraController cc)
    {
        var pose = cc.pose_in_reference_frame;
        body_frame = pose;
    }

    public override void TeleportToNewCenter(Vector3 pos, Vector3 up)
    {
        var current_direction = body_frame.Forward();
        var new_pos = pos - current_direction * 10;
        body_frame.position = new_pos;
        body_frame.SetUp(up);
    }

    public override void ApplyRightMove(UniversalCameraController cc)
    {
        bool is_shift_pressed = Input.GetKey(KeyCode.LeftShift);
        var normal_vector = is_shift_pressed
            ? cc.PoseOfReferenceFrame().ProjectToHorizon(Camera.main.transform.forward).normalized
            : cc.PoseOfReferenceFrame().Up();

        var plane_over_global_right_pressed = NavigationPlane(cc, normal_vector);
        var ray = Camera.main.ScreenPointToRay(Input.mousePosition);

        float enter;
        if (plane_over_global_right_pressed.Raycast(ray, out enter))
        {
            var hit_point = ray.GetPoint(enter);
            var hit_point_in_reference_frame = cc.PositionInReferencedFrame(hit_point);
            var delta = hit_point_in_reference_frame - cc.touch_position_in_reference_frame;

            body_frame.position -= (delta * (Time.deltaTime / TimeConstant));
        }
    }

    public override void ApplyWheelMove(UniversalCameraController cc)
    {
        var normal_vector = -Camera.main.transform.forward;

        var plane_over_global_wheel_pressed = NavigationPlane(cc, normal_vector);
        var ray = Camera.main.ScreenPointToRay(Input.mousePosition);

        float enter;
        if (plane_over_global_wheel_pressed.Raycast(ray, out enter))
        {
            var hit_point = ray.GetPoint(enter);
            var hit_point_in_reference_frame = cc.PositionInReferencedFrame(hit_point);
            var delta = hit_point_in_reference_frame - cc.touch_position_in_reference_frame;

            var delta_in_global_frame = cc.PoseOfReferenceFrame().TransformDirection(delta);
            var delta_in_camera_frame = Camera.main.transform.InverseTransformDirection(
                delta_in_global_frame
            );

            var x = delta_in_camera_frame.x;
            var y = delta_in_camera_frame.y;

            var rad = (hit_point - Camera.main.transform.position).magnitude;

            var xangle = x / rad;
            var yangle = y / rad;

            var sens = 20.0f;
            var currotation = body_frame.rotation;
            var euler = currotation.eulerAngles;
            var yaw = euler.y;
            var pitch = euler.x > 180.0f ? euler.x - 360.0f : euler.x;

            pitch = Mathf.Clamp(pitch, -75, 75);

            yaw -= xangle * sens;
            pitch += yangle * sens;

            var newrotation = Quaternion.Euler(pitch, yaw, 0);
            body_frame.rotation = newrotation;
        }
    }

    void RotateCameraWithCenter(
        Vector3 center,
        float angle,
        float verical_angle,
        UniversalCameraController cc
    )
    {
        var center_frame = body_frame;
        center_frame.position = center;
        var body_frame_in_center = center_frame.Inverse() * body_frame;
        var diffpose = new Pose(new Vector3(0, 0, 0), Quaternion.Euler(verical_angle, angle, 0));
        var new_body_frame_in_center = diffpose * body_frame_in_center;
        body_frame = center_frame * new_body_frame_in_center;

        // body_frame = center_frame.Inverse() * center_frame * body_frame;
        body_frame.Normalize();

        // var newpos = Quaternion.Euler(verical_angle, angle, 0) * diffpos;
        // var rdelta = newpos - diffpos;
        // body_frame.position += rdelta;
        // var camera_rot = body_frame.rotation;
        // var newrot = Quaternion.Euler(verical_angle, angle, 0) * camera_rot;
        // body_frame.rotation = newrot;

        body_frame.rotation = Quaternion.LookRotation(body_frame.Forward(), Vector3.up);
    }

    public override void ApplyAltRotation(UniversalCameraController cc, float signal, float signal2)
    {
        var center = cc.touch_position_in_reference_frame;
        RotateCameraWithCenter(center, signal, signal2, cc);
    }

    public override void ApplyScroll(UniversalCameraController cc, float signal)
    {
        var forward = body_frame.Forward();
        body_frame.position += forward * signal;
    }
}

public class RingNavigateModule : HorizonNavigateModule
{
    Pose rotation_frame = Pose.Identity;
    Pose body_frame = Pose.Identity;

    public override void ReInitFromCameraPose(UniversalCameraController cc)
    {
        var pose = cc.pose_in_reference_frame;
        body_frame = pose;
        rotation_frame = Pose.Identity;
    }

    public override void RestoreCameraPose(UniversalCameraController cc)
    {
        cc.pose_in_reference_frame = rotation_frame * body_frame;
    }

    float DownizeAngle(Pose pose)
    {
        var down = -pose.Up();

        var x = -down.x;
        var y = -down.y;

        var angle = Mathf.Atan2(x, y);
        //Debug.Log("DownizeAngle: " + angle + "x: " + x + " y: " + y);
        return angle * Mathf.Rad2Deg;
    }

    Vector3 DownizeVector(Vector3 vector)
    {
        var r = new Vector3(vector.x, vector.y, 0);
        return r.normalized;
    }

    Quaternion ZRQuat(Pose pose)
    {
        var z_angle_in_rframe = DownizeAngle(pose);
        var z_angle_in_rframe_quat = Quaternion.Euler(0, 0, z_angle_in_rframe);
        return z_angle_in_rframe_quat;
    }

    Quaternion ZRQuatInv(Pose pose)
    {
        var z_angle_in_rframe = DownizeAngle(pose);
        var z_angle_in_rframe_quat = Quaternion.Euler(0, 0, -z_angle_in_rframe);
        return z_angle_in_rframe_quat;
    }

    public override void ApplyScroll(UniversalCameraController cc, float signal)
    {
        var forward = body_frame.Forward();
        body_frame.position += forward * signal;
    }

    void ApplyZDiff(UniversalCameraController cc, float zdiff)
    {
        body_frame.position += Vector3.forward * zdiff;
    }

    void ApplyYDiff(UniversalCameraController cc, float ydiff)
    {
        body_frame.position += Vector3.up * ydiff;
    }

    void ApplyXDiffLinear(UniversalCameraController cc, float xdiff)
    {
        body_frame.position += Vector3.right * xdiff;
    }

    void ApplyXDiffRotation(UniversalCameraController cc, float xdiff, float radius)
    {
        var delta_radial_angle = xdiff / radius;
        var delta_radial_angle_deg = delta_radial_angle * Mathf.Rad2Deg;
        var rquat = Quaternion.Euler(0, 0, delta_radial_angle_deg);
        var rpose = new Pose(new Vector3(0, 0, 0), rquat);
        rotation_frame = rpose * rotation_frame;
    }

    public override void ApplyRightMove(UniversalCameraController cc)
    {
        // if (Input.GetKey(KeyCode.LeftShift))
        // {
        // 	base.ApplyRightMove(cc);
        // 	return;
        // }

        bool is_shift_pressed = Input.GetKey(KeyCode.LeftShift);
        var normal_vector = is_shift_pressed
            ? cc.PoseOfReferenceFrame().Forward()
            : (cc.PoseOfReferenceFrame() * rotation_frame).Up();

        var plane_over_global_right_pressed = NavigationPlane(cc, normal_vector);
        var ray = Camera.main.ScreenPointToRay(Input.mousePosition);

        float enter;
        if (plane_over_global_right_pressed.Raycast(ray, out enter))
        {
            var z_angle_in_rframe_quat = ZRQuat(cc.pose_in_reference_frame);

            var hit_point = ray.GetPoint(enter);
            var hit_point_in_reference_frame = cc.PositionInReferencedFrame(hit_point);
            var delta = hit_point_in_reference_frame - cc.touch_position_in_reference_frame;

            var rdelta = z_angle_in_rframe_quat * delta;

            var project_to_axis = rdelta.z;
            var project_to_radial = rdelta.x;
            var project_to_up = rdelta.y;

            ApplyYDiff(cc, -project_to_up * (Time.deltaTime / TimeConstant));
            ApplyZDiff(cc, -project_to_axis * (Time.deltaTime / TimeConstant));

            if (is_shift_pressed)
            {
                ApplyXDiffLinear(cc, -project_to_radial * (Time.deltaTime / TimeConstant));
            }
            else
            {
                var hframe_yx = new Vector2(
                    hit_point_in_reference_frame.x,
                    hit_point_in_reference_frame.y
                );
                var radius = hframe_yx.magnitude;
                ApplyXDiffRotation(
                    cc,
                    -project_to_radial * (Time.deltaTime / TimeConstant),
                    radius
                );
            }
        }
    }

    void RotateCameraWithCenter(
        Vector3 center,
        float angle,
        float signal2,
        UniversalCameraController cc
    )
    {
        var camera_pos = body_frame.position;
        var diffpos = camera_pos - center;
        var newpos = Quaternion.Euler(0, angle, 0) * diffpos;
        //body_frame.position = (center + newpos);

        var rdelta = newpos - diffpos;

        var project_to_axis = rdelta.z;
        var project_to_radial = rdelta.x;
        var project_to_up = rdelta.y;

        var hframe_yx = new Vector2(center.x, center.y);
        var radius = hframe_yx.magnitude;

        ApplyZDiff(cc, project_to_axis);
        ApplyXDiffLinear(cc, project_to_radial);

        var camera_rot = body_frame.rotation;
        var newrot = Quaternion.Euler(0, angle, 0) * camera_rot;
        body_frame.rotation = newrot;
    }

    public override void ApplyAltRotation(UniversalCameraController cc, float signal, float signal2)
    {
        var center = rotation_frame.InverseTransformPoint(cc.touch_position_in_reference_frame);
        RotateCameraWithCenter(center, signal, signal2, cc);
    }

    public override void TeleportToNewCenter(Vector3 pos, Vector3 up)
    {
        var pos_in_rotate_frame = rotation_frame.InverseTransformPoint(pos);
        var up_in_rotate_frame = rotation_frame.InverseTransformDirection(up);

        var current_direction = body_frame.Forward();
        var new_pos = pos_in_rotate_frame - current_direction * 10;
        body_frame.position = new_pos;
        body_frame.SetUp(up_in_rotate_frame);
    }

    public override void ApplyWheelMove(UniversalCameraController cc)
    {
        var normal_vector = -Camera.main.transform.forward;

        var plane_over_global_wheel_pressed = NavigationPlane(cc, normal_vector);
        var ray = Camera.main.ScreenPointToRay(Input.mousePosition);

        float enter;
        if (plane_over_global_wheel_pressed.Raycast(ray, out enter))
        {
            var hit_point = ray.GetPoint(enter);
            var hit_point_in_reference_frame = cc.PositionInReferencedFrame(hit_point);
            var delta = hit_point_in_reference_frame - cc.touch_position_in_reference_frame;

            var delta_in_global_frame = cc.PoseOfReferenceFrame().TransformDirection(delta);
            var delta_in_camera_frame = Camera.main.transform.InverseTransformDirection(
                delta_in_global_frame
            );

            var x = delta_in_camera_frame.x;
            var y = delta_in_camera_frame.y;

            var rad = (hit_point - Camera.main.transform.position).magnitude;

            var xangle = x / rad;
            var yangle = y / rad;

            var sens = 20.0f;
            //var refrotation = cc.pose_in_reference_frame.rotation;
            //var currotation = ZRQuat(cc.pose_in_reference_frame) * refrotation;
            //var currotation = refrotation;
            var currotation = body_frame.rotation;

            var euler = currotation.eulerAngles;
            var yaw = euler.y;
            var pitch = euler.x > 180.0f ? euler.x - 360.0f : euler.x;
            pitch = Mathf.Clamp(pitch, -75, 75);

            yaw -= xangle * sens;
            pitch += yangle * sens;

            var newrotation = Quaternion.Euler(pitch, yaw, 0);
            //newrotation = ZRQuatInv(cc.pose_in_reference_frame) *
            //	newrotation;
            body_frame.rotation = newrotation;
        }
    }
}

public class UniversalCameraController : AbstractCameraController
{
    protected const float MaxTouchDist = 50.0f;

    float _scroll_accum = 0.0f;

    //float _x_rotate_accum = 0.0f;
    //float _y_rotate_accum = 0.0f;
    float _scroll_sensitive = 2.0f;

    //float _rotate_sensitive = 5.0f;

    bool right_pressed = false;
    bool wheel_pressed = false;

    public Vector3 touch_position_in_reference_frame;

    public Pose pose_in_reference_frame;

    // public Pose smooth_pose_in_reference_frame;
    // float smooth_time_constant = 1.0f;

    NavigateModule navigate_module;

    public Pose PoseOfReferenceFrame()
    {
        return TransformToPose(reference_frame);
    }

    public Vector3 PositionInReferencedFrame(Vector3 position)
    {
        var reference_frame_pose = TransformToPose(reference_frame);
        var position_in_reference_frame = reference_frame_pose.InverseTransformPoint(position);
        return position_in_reference_frame;
    }

    public override void TeleportToNewCenter(Vector3 pos, Vector3 up)
    {
        pos = PositionInReferencedFrame(pos);
        up = reference_frame.InverseTransformDirection(up);
        navigate_module.TeleportToNewCenter(pos, up);

        // обновляем позицию камеры
        // для совместимости со сменой опорного фрейма
        navigate_module.RestoreCameraPose(this);
        UpdateMyPosition();
    }

    public override void ChangeReferencedFrame(Transform frame)
    {
        reference_frame = frame;
        ReevaluatePoseInReferenceFrame();
        navigate_module = new HorizonNavigateModule();
        navigate_module.ReInitFromCameraPose(this);
    }

    NavigateModule MakeNavigateModuleForFrame(Transform frame)
    {
        var rotplatform = frame.GetComponent<RotatedPlatformView>();
        if (rotplatform != null)
        {
            return new RingNavigateModule();
        }
        else
        {
            return new HorizonNavigateModule();
        }
    }

    void Awake()
    {
        _instance = this;
        if (reference_frame != null)
        {
            var pose = TransformToPose(this.transform);
            var reference_frame_pose = TransformToPose(reference_frame);
            pose_in_reference_frame = reference_frame_pose.Inverse() * pose;
            navigate_module = MakeNavigateModuleForFrame(reference_frame);
            navigate_module.ReInitFromCameraPose(this);
        }
        else
        {
            pose_in_reference_frame = TransformToPose(this.transform);
            navigate_module = new HorizonNavigateModule();
            navigate_module.ReInitFromCameraPose(this);
        }
    }

    public void ReevaluatePoseInReferenceFrame()
    {
        var pose = TransformToPose(this.transform);
        var reference_frame_pose = TransformToPose(reference_frame);
        pose_in_reference_frame = reference_frame_pose.Inverse() * pose;
    }

    Pose TransformToPose(Transform transform)
    {
        if (transform == null)
        {
            return Pose.Identity;
        }

        Pose pose = new Pose();
        pose.position = transform.position;
        pose.rotation = transform.rotation;
        return pose;
    }

    void ApplyScroll()
    {
        if (_scroll_accum != 0)
        {
            float signal = _scroll_accum * (4.0f * Time.deltaTime);
            _scroll_accum -= signal;

            navigate_module.ApplyScroll(this, signal * _scroll_sensitive);
        }
    }

    Vector2 _alt_accum = Vector2.zero;
    float _alt_sensitive = 0.05f;

    void ApplyAlt()
    {
        if (_alt_accum != Vector2.zero)
        {
            var signal = _alt_accum * (4.0f * Time.deltaTime);
            _alt_accum -= signal;
            navigate_module.ApplyAltRotation(
                this,
                signal.x * _alt_sensitive,
                signal.y * _alt_sensitive
            );
        }
    }

    // void MouseWheelProcedure()
    // {
    // 	if (Input.GetMouseButton(2)) {
    // 		var x = Input.GetAxis("Mouse X");
    // 		var y = Input.GetAxis("Mouse Y");
    // 		_x_rotate_accum += x;
    // 		_y_rotate_accum += y;
    // 	}
    // }

    // void ApplyRotate()
    // {
    // 	var x = _x_rotate_accum * (16.0f * Time.deltaTime);
    // 	var y = _y_rotate_accum * (16.0f * Time.deltaTime);
    // 	navigate_module.RotateCamera(this,
    // 			-x * _rotate_sensitive,
    // 			y * _rotate_sensitive);
    // 	_x_rotate_accum -= x;
    // 	_y_rotate_accum -= y;
    // }

    bool alt_pressed = false;
    Vector3 alt_pressed_os_position;
    public Vector3 alt_pressed_world_position;
    public Vector3 alt_pressed_mouse_position;

    // void SetTargetPosition(Vector3 pos)
    // {
    // 	// if (_camera_bounds != null)
    // 	// {
    // 	// 	if (!_camera_bounds.IsValid(pos))
    // 	// 	{
    // 	// 		return;
    // 	// 	}
    // 	// }

    // 	transform.position = pos;
    // 	//target_position = pos;
    // }


    // public void SaveAngles()
    // {
    // 	var camera_rot = this.transform.rotation;
    // //	yaw = camera_rot.eulerAngles.y;
    // //	pitch = camera_rot.eulerAngles.x;
    // }

    void AltProcedure()
    {
        if (Input.GetKey(KeyCode.LeftAlt))
        {
            if (alt_pressed == false)
            {
                Cursor.visible = false;
                alt_pressed_mouse_position = Input.mousePosition;
                // alt_pressed_world_position =
                // 	GameCore.camera_point_to_world_position(
                // 		alt_pressed_mouse_position);
                SaveTouchPosition(20.0f);

                POINT p;
                GetCursorPos(out p);
                alt_pressed_os_position = new Vector3(p.X, p.Y, 0);
                Cursor.visible = false;

                // disable mouse cursor
            }
            else
            {
                var mouse_position = Input.mousePosition;
                var diff = mouse_position - alt_pressed_mouse_position;
                var diff_x = diff.x;
                var diff_y = diff.y;
                _alt_accum += new Vector2(diff_x, -diff_y);
                SetCursorPos((int)alt_pressed_os_position.x, (int)alt_pressed_os_position.y);
            }
            alt_pressed = true;
        }
        else
        {
            Cursor.visible = true;
            alt_pressed = false;
        }
    }

    public override void LateUpdateImpl()
    {
        if (Input.GetKey(KeyCode.LeftControl))
        {
            return;
        }

        MouseScrollProcedure();
        ApplyScroll();

        //if (Input.GetMouseButton(1))
        RightMouseButtonProcedure();
        //else if (Input.GetMouseButton(2))

        WhellButtonProcedure();

        AltProcedure();
        ApplyAlt();

        UpdateGlobalShaderVariables();
        navigate_module.RestoreCameraPose(this);
        UpdateMyPosition();
    }

    void UpdateMyPosition()
    {
        // var error = smooth_pose_in_reference_frame.Inverse() * pose_in_reference_frame;
        // var pos_error = error.position;
        // var rot_error = error.rotation;
        // smooth_pose_in_reference_frame.position +=
        // 	pos_error * (Time.deltaTime / smooth_time_constant);
        // error.rotation.ToAngleAxis(out var error_axis, out var error_angle);
        // error_angle = error_angle * (Time.deltaTime / smooth_time_constant);
        // var error_quat = Quaternion.AngleAxis(error_axis, error_angle);
        // smooth_pose_in_reference_frame.rotation =
        // 	error_quat * smooth_pose_in_reference_frame.rotation;

        // Pose reference_frame_pose = TransformToPose(reference_frame);
        // Pose pose = reference_frame_pose * smooth_pose_in_reference_frame;
        // this.transform.position = pose.position;
        // this.transform.rotation = pose.rotation;

        Pose reference_frame_pose = TransformToPose(reference_frame);
        Pose pose = reference_frame_pose * pose_in_reference_frame;
        this.transform.position = pose.position;
        this.transform.rotation = pose.rotation;
    }

    // static protected Vector3 CorrectGlobalTouchPosition(
    // 	UniversalCameraController cc, Vector3 global_position)
    // {
    // 	var diff = global_position -
    // 		Camera.main.transform.position;
    // 	var dist = diff.magnitude;
    // 	if (dist > MaxTouchDist)
    // 	{
    // 		dist = MaxTouchDist;
    // 		global_position =
    // 			Camera.main.transform.position + diff.normalized * dist;
    // 	}
    // 	return global_position;
    // }

    void SaveTouchPosition(float maxdist = MaxTouchDist)
    {
        try
        {
            RaycastHit hit;
            Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
            Vector3 point;
            if (Physics.Raycast(ray, out hit, maxdist))
            {
                point = hit.point;
            }
            else
            {
                point = ray.GetPoint(maxdist);
            }
            touch_position_in_reference_frame = PositionInReferencedFrame(point);
        }
        catch
        {
            return;
        }
    }

    public Vector3 TouchWorldPosition()
    {
        return PoseOfReferenceFrame().TransformPoint(touch_position_in_reference_frame);
    }

    public void RightMouseButtonProcedure()
    {
        if (Input.GetMouseButton(1))
        {
            if (!right_pressed)
            {
                SaveTouchPosition();
            }
            else
            {
                navigate_module.ApplyRightMove(this);
            }
            right_pressed = true;
        }
        else
        {
            right_pressed = false;
        }
    }

    public void WhellButtonProcedure()
    {
        if (Input.GetMouseButton(2))
        {
            if (!wheel_pressed)
            {
                SaveTouchPosition();
            }
            else
            {
                navigate_module.ApplyWheelMove(this);
            }
            wheel_pressed = true;
        }
        else
        {
            wheel_pressed = false;
        }
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
                float scroll = Input.mouseScrollDelta.y;
                if (scroll != 0)
                    GameCore.on_mouse_wheel_time_control(scroll);
            }
            else
            {
                float scroll = Input.mouseScrollDelta.y;
                if (scroll != 0)
                {
                    float y;
                    if (scroll > 0)
                    {
                        y = 1.0f;
                    }
                    else
                    {
                        y = -1.0f;
                    }
                    _scroll_accum += y;
                }
            }
        }
    }

    public void UpdateGlobalShaderVariables()
    {
        var inverseProjectionMatrix = GetInverseProjectionMatrix();
        var inverseViewMatrix = GetInverseViewMatrix();
        Shader.SetGlobalMatrix("InverseViewMatrix", inverseViewMatrix);
        Shader.SetGlobalMatrix("InverseProjectionMatrix", inverseProjectionMatrix);
    }
}
