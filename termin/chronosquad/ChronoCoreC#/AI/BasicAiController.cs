using System.Collections.Generic;
using UnityEngine;

public class BasicAiController : AiController
{
    public float DistractSpeed = 3.0f;
    int _confused_counter = 0;

    MyList<BasicAiCommanderSlot> _commanders = new MyList<BasicAiCommanderSlot>();
    public DistructState _distruct_state = new DistructState(
        0.0f,
        long.MinValue / 2,
        DistructStateEnum.Green,
        1.0f
    );

    public bool IsDistruct()
    {
        return !_distruct_state.IsGreen();
    }

    public override bool IsAlarmState()
    {
        return attention_module.IsPanic();
    }

    public override bool IsQuestionState()
    {
        return attention_module.IsPanic();
    }

    // public AttentionModule AttentionModule()
    // {
    // 	return attention_module;
    // }

    public void IncrementConfusedCounter()
    {
        _confused_counter++;
    }

    public void DecrementConfusedCounter()
    {
        _confused_counter--;
    }

    public override void ConfusedWhileGrabbedAnother(long duration, ObjectId grabber)
    {
        var step = actor.LocalStep();
        var event_card = new TemporaryIncrementConfusedCounterCard(step, step + duration);
        actor.AddCard(event_card);
        CommandBuffer().MarkAllCommandsAsFinished();

        var cmd = new GrubbedWhileAliveCommand(
            AnimationType.Idle,
            actor.LocalStep() + 1,
            confusion_time: 6.0f,
            host_actor: grabber
        );
        actor.AddExternalCommand(cmd);
    }

    public void AddCommander(BasicAiCommander commander, string name, int priority)
    {
        _commanders.Add(
            new BasicAiCommanderSlot(commander: commander, name: name, priority: priority)
        );
        SortCommanders();
    }

    public void SortCommanders()
    {
        // sort by priority in descending order
        _commanders.Sort((x, y) => y.priority.CompareTo(x.priority));
    }

    public override string Info()
    {
        string result = base.Info();
        result += "AttentionModule: " + attention_module.Info() + "\n";
        result += "DistructState: " + _distruct_state.Info() + "\n";
        result += "Commanders: \n";
        foreach (var commander in _commanders)
        {
            result += commander.commander.Info() + "\n";
        }
        return result;
    }

    public override AiController Copy(ObjectOfTimeline newactor)
    {
        BasicAiController buf = new BasicAiController(newactor);
        buf.CopyFrom(this, newactor);
        return buf;
    }

    public virtual void CopyFrom(BasicAiController other, ObjectOfTimeline newactor)
    {
        base.CopyFrom(other, newactor);
        attention_module = new AttentionModule(other.attention_module);
        _distruct_state = other._distruct_state;
        _commanders = new MyList<BasicAiCommanderSlot>();
        foreach (var commander in other._commanders)
        {
            _commanders.Add(
                new BasicAiCommanderSlot(
                    commander: commander.commander.Copy(),
                    name: commander.name,
                    priority: commander.priority
                )
            );
        }
    }

    public BasicAiCommander GetCommander(string name)
    {
        foreach (var commander in _commanders)
        {
            if (commander.name == name)
                return commander.commander;
        }
        return null;
    }

    public T GetCommander<T>(string name) where T : BasicAiCommander
    {
        foreach (var commander in _commanders)
        {
            if (commander.name == name)
                return (T)commander.commander;
        }
        return null;
    }

    public T GetCommander<T>() where T : BasicAiCommander
    {
        foreach (var commander in _commanders)
        {
            if (commander.commander is T)
                return (T)commander.commander;
        }
        return null;
    }

    public CommandBufferBehaviour CommandBuffer()
    {
        return actor.CommandBuffer();
    }

    override public void DropToCurrentState(long local_step)
    {
        attention_module.DropToCurrentState(local_step);
        base.DropToCurrentState(local_step);
    }

    override public void DropToCurrentStateInverted(long local_step)
    {
        attention_module.DropToCurrentStateInverted(local_step);
        base.DropToCurrentStateInverted(local_step);
    }

    public BasicAiController(ObjectOfTimeline obj) : base(obj) { }

    public override void Promote(long curstep, ITimeline tl)
    {
        base.Promote(curstep, tl);
        attention_module.Promote(curstep);
        foreach (var commander in _commanders)
        {
            commander.commander.Promote(curstep);
        }
    }

    public override void CleanArtifacts()
    {
        _distruct_state = new DistructState(
            0.0f,
            long.MinValue / 2,
            DistructStateEnum.Green,
            DistractSpeed
        );
    }

    override public void HearNoise(
        long step,
        ReferencedPoint center,
        RestlessnessParameters noise_parameters
    )
    {
        AddCard(
            new HearLoudSoundStateEvent(
                step: step,
                source: center,
                noise_parameters: noise_parameters
            )
        );
    }

    public void StartDistruct(bool very_small)
    {
        var new_distruct_state = new DistructState(
            _distruct_state.Level(GetObject().LocalStep()),
            actor.LocalStep(),
            DistructStateEnum.Yellow,
            DistractSpeed / (very_small ? 5.0f : 1.0f)
        );
        var event_card = new DistructStateChangeEvent(GetObject().LocalStep())
        {
            prevstate = _distruct_state,
            nextstate = new_distruct_state
        };

        AddChange(event_card);
    }

    public void RedDistruct()
    {
        var new_distruct_state = new DistructState(
            _distruct_state.Level(GetObject().LocalStep()),
            actor.LocalStep(),
            DistructStateEnum.Red,
            DistractSpeed
        );
        var event_card = new DistructStateChangeEvent(GetObject().LocalStep())
        {
            prevstate = _distruct_state,
            nextstate = new_distruct_state
        };

        AddChange(event_card);
    }

    public void VioletDistruct()
    {
        var new_distruct_state = new DistructState(
            _distruct_state.Level(GetObject().LocalStep()),
            actor.LocalStep(),
            DistructStateEnum.Violet,
            DistractSpeed
        );
        var event_card = new DistructStateChangeEvent(GetObject().LocalStep())
        {
            prevstate = _distruct_state,
            nextstate = new_distruct_state
        };

        AddChange(event_card);
    }

    public void StopDistruct()
    {
        var new_distruct_state = new DistructState(
            _distruct_state.Level(GetObject().LocalStep()),
            actor.LocalStep(),
            DistructStateEnum.Green,
            DistractSpeed
        );
        var event_card = new DistructStateChangeEvent(GetObject().LocalStep())
        {
            prevstate = _distruct_state,
            nextstate = new_distruct_state
        };

        AddChange(event_card);
    }

    public void SetDistructState(DistructState state)
    {
        _distruct_state = state;
    }

    public bool DistructStartOnThatStep()
    {
        var step = GetObject().LocalStep();
        return _distruct_state.start_step == step;
    }

    public DistructStatus DistructLevel()
    {
        return new DistructStatus(
            _distruct_state.Level(GetObject().LocalStep()),
            _distruct_state.distruct_type
        );
    }

    public bool IsRedDistruct()
    {
        return _distruct_state.distruct_type == DistructStateEnum.Red;
    }

    public bool IsVioletDistruct()
    {
        return _distruct_state.distruct_type == DistructStateEnum.Violet;
    }

    public bool IsYellowDistruct()
    {
        return _distruct_state.distruct_type == DistructStateEnum.Yellow;
    }

    protected void CommandReaction(long timeline_step, long local_step, ITimeline timeline)
    {
        foreach (var commander in _commanders)
        {
            bool prevent = commander.commander.WhatIShouldDo(this, timeline_step, local_step);
            if (prevent)
                return;
        }
    }

    public override void Execute(long timeline_step, long local_step, ITimeline timeline)
    {
        if (!_is_enabled)
            return;

        if (_confused_counter > 0)
        {
            return;
        }

        var current_command = GetObject().CurrentCommand();
        if (current_command != null && !current_command.CanBeInterrupted())
            return;

        CommandReaction(timeline_step, local_step, timeline);
    }

    public AttentionModule Attention()
    {
        return attention_module;
    }

    public bool IsEqual(BasicAiController other)
    {
        if (!base.IsEqual(other))
            return false;

        if (_commanders.Count != other._commanders.Count)
            return false;

        for (int i = 0; i < _commanders.Count; i++)
        {
            if (!_commanders[i].IsEqual(other._commanders[i]))
                return false;
        }

        if (!attention_module.IsEqual(other.attention_module))
            return false;

        if (!_distruct_state.IsEqual(other._distruct_state))
            return false;

        return true;
    }
}
