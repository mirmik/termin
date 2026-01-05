using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public enum PatrolState
{
    None,
    Panic,
    Attack,
    Interested
}

public abstract class PatrolStateEvent : AiControllerEvent
{
    public PatrolStateEvent(long step) : base(step, step + 1) { }

    public PatrolStateEvent(long sstep, long fstep) : base(sstep, fstep) { }

    protected BasicAiController Behaviour(ObjectOfTimeline actor)
    {
        return actor.AiController() as BasicAiController;
    }

    protected AttentionModule AttentionModule(ObjectOfTimeline actor)
    {
        return Behaviour(actor).attention_module;
    }
}

public struct DistructStatus
{
    public float level;
    public DistructStateEnum type;

    public DistructStatus(float level, DistructStateEnum type)
    {
        this.level = level;
        this.type = type;
    }
}

public enum DistructStateEnum
{
    Yellow,
    Red,
    Green,
    Violet
}

public class DistructState
{
    public float distruct_accumulator_start = 0.0f;
    public long start_step = long.MinValue;
    float DistractSpeed = 1.0f;
    public DistructStateEnum distruct_type = DistructStateEnum.Green;

    // public DistructState(DistructState other)
    // {
    // 	distruct_accumulator_start = other.distruct_accumulator_start;
    // 	start_step = other.start_step;
    // 	distruct_type = other.distruct_type;
    // }

    public string Info()
    {
        return "DistructState: "
            + distruct_accumulator_start
            + " "
            + start_step
            + " "
            + distruct_type;
    }

    public DistructState(
        float distruct_accumulator_start,
        long start_step,
        DistructStateEnum type,
        float DistractSpeed
    )
    {
        this.distruct_accumulator_start = distruct_accumulator_start;
        this.start_step = start_step;
        this.distruct_type = type;
        this.DistractSpeed = DistractSpeed;
    }

    public bool IsEqual(DistructState other)
    {
        return distruct_accumulator_start == other.distruct_accumulator_start
            && start_step == other.start_step
            && distruct_type == other.distruct_type;
    }

    public bool IsGreen()
    {
        return distruct_type == DistructStateEnum.Green;
    }

    float Mul()
    {
        return IsGreen() ? -DistractSpeed : DistractSpeed;
    }

    public float Level(long current_step)
    {
        float e = distruct_accumulator_start + Mul() * (current_step - start_step) * 0.1f;
        if (e < 0.0f)
            e = 0.0f;

        return e;
    }
}
