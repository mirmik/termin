using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public enum TrajectoryType
{
    Straight,
    Parabolic
}

public abstract class ParabolicAction : OneAbilityAction
{
    public Material material;
    public float EffectRadius = 5;
    public float LoudRadius = 5;
    public float ThrowRadius = 10;

    TrajectoryType trajectory_type = TrajectoryType.Parabolic;

    //GameObject _circle_renderer_object;

    public float horizontal_speed = 2;

    public ParabolicAction(KeyCode keycode) : base(keycode) { }

    public override string TooltipText()
    {
        return "Бросить НЕЧТО";
    }

    public void SetTrajectoryType(TrajectoryType type)
    {
        trajectory_type = type;
    }

    public override void OnIconClick()
    {
        _gun_clicked = true;
        _line_renderer.enabled = true;
        UsedActionBuffer.Instance.SetUsedAction(this);
    }

    public override void Cancel()
    {
        UsedActionBuffer.Instance.SetUsedAction(null);
        _gun_clicked = false;
        _line_renderer.enabled = false;
        ProgramBlueCammeraEffect(false, this.transform.position, LoudRadius);
        ProgramZoneCammeraEffect(false, this.transform.position, ThrowRadius);
        ProgramEffectExtension(false, this.transform.position);
    }

    MyList<Vector3> parabolic_trajectory(Vector3 start_position, Vector3 finish_position)
    {
        float g = 9.8f;
        Vector2 start_position_2d = new Vector2(start_position.x, start_position.z);
        Vector2 finish_position_2d = new Vector2(finish_position.x, finish_position.z);
        Vector2 direction = finish_position_2d - start_position_2d;
        float distance = direction.magnitude;
        float time = distance / horizontal_speed;

        float vertical_dist = finish_position.y - start_position.y;
        // y = v0 * t - g * t^2 / 2
        // v0 = (y + g * t^2 / 2) / t
        float vertical_speed = (vertical_dist + g * time * time / 2) / time;

        MyList<Vector3> arr = new MyList<Vector3>();
        for (float t = 0; (t - time) < 1e-5; t += 0.1f)
        {
            float x = start_position.x + horizontal_speed * t * direction.x / distance;
            float y = start_position.y + vertical_speed * t - g * t * t / 2;
            float z = start_position.z + horizontal_speed * t * direction.y / distance;
            arr.Add(new Vector3(x, y, z));
        }

        // add last point
        arr.Add(finish_position);
        return arr;
    }

    MyList<Vector3> straight_trajectory(Vector3 start_position, Vector3 finish_position)
    {
        MyList<Vector3> arr = new MyList<Vector3>();
        arr.Add(start_position);
        arr.Add(finish_position);
        return arr;
    }

    MyList<Vector3> MakeTrajectory(Vector3 start_position, Vector3 finish_position)
    {
        if (trajectory_type == TrajectoryType.Straight)
            return straight_trajectory(start_position, finish_position);
        else
            return parabolic_trajectory(start_position, finish_position);
    }

    public override void UpdateActive()
    {
        if (_gun_clicked)
        {
            _line_renderer.startWidth = LineWidth;
            _line_renderer.endWidth = LineWidth;
            //_line_renderer.SetPosition(0, this.transform.position + new Vector3(0, 1, 0));
            Vector3 start_position = this.transform.position + new Vector3(0, 1, 0);

            Vector3 mouse_pos = Input.mousePosition;

            ProgramZoneCammeraEffect(true, this.transform.position, ThrowRadius);

            var click = GameCore.CursorHit(mouse_pos);
            var hit = click.environment_hit;

            if (hit.collider != null)
            {
                Vector3 world_pos = hit.point;
                Vector3 finish_position = world_pos;

                MyList<Vector3> arr = MakeTrajectory(start_position, finish_position);
                _line_renderer.positionCount = arr.Count;

                for (int i = 0; i < arr.Count; i++)
                {
                    _line_renderer.SetPosition(i, arr[i]);
                }

                float distance = Vector3.Distance(start_position, finish_position);
                if (distance > ThrowRadius)
                {
                    DisableEffectRings();
                }
                else
                {
                    ProgramBlueCammeraEffect(true, finish_position, LoudRadius);
                    ProgramEffectExtension(true, finish_position);
                }
            }
            else
            {
                DisableEffectRings();
                _line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
            }
        }
    }

    public float Distance(Vector3 pos)
    {
        var pos_xy = new Vector2(pos.x, pos.z);
        var actor_pos_xy = new Vector2(this.transform.position.x, this.transform.position.z);
        return Vector2.Distance(pos_xy, actor_pos_xy);
    }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        if (Distance(click.environment_hit.point) > ThrowRadius)
        {
            return;
        }

        ParabolicActionPrivateParameters parameters = new ParabolicActionPrivateParameters(
            new ParabolicCurve3d(this.transform.position, click.environment_hit.point, 4.0f),
            1.0f
        );

        var frame = GameCore.FrameNameForPosition(click.environment_hit.point);
        Debug.Log("Frame: " + frame);
        var sability = GetAbility();
        sability.UseOnEnvironment(
            ReferencedPoint.FromGlobalPosition(
                click.environment_hit.point,
                frame,
                _actor.GetObject().GetTimeline()
            ),
            _actor.GetObject().GetTimeline(),
            _actor.GetObject().AbilityListPanel(),
            private_parameters: parameters
        );
        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        if (actor == this.gameObject)
        {
            Cancel();
            return;
        }

        OnEnvironmentClick(click);
        return;
    }
}
