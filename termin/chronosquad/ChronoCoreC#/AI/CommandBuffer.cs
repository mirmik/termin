using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class CommandBufferBehaviour // : ActorBehaviour
{
    protected ObjectOfTimeline actor;
    MyList<ActorCommand> commands_added = new MyList<ActorCommand>(); // < TODO: Заменить на очередь

    bool _controlled_by_ai = false;

    ActorCommand external_command_one_buffer = null;
    long marked_as_finished_step = long.MinValue;

    ActionList<ActorCommand> command_queue;

    //ActorCommand last_executed_command = null;

    public Actor Actor()
    {
        return actor as Actor;
    }

    public ObjectOfTimeline Object()
    {
        return actor;
    }

    public MyList<ActorCommand> CommandsAdded => commands_added;

    public void SetControlledByAi(bool value)
    {
        _controlled_by_ai = value;
    }

    bool CleanBufferOnDrop()
    {
        return _controlled_by_ai;
    }

    public void CleanArtifacts() { }

    public void Clean()
    {
        command_queue.Clean();
    }

    public CommandBufferBehaviour(ObjectOfTimeline actor)
    {
        this.actor = actor;
        command_queue = new ActionList<ActorCommand>(true);
    }

    public void Promote(long local_step, ITimeline tl)
    {
        InternalPromote(local_step, tl);
    }

    public void InternalPromote(long local_step, ITimeline tl)
    {
        MyList<ActorCommand> added;
        MyList<ActorCommand> gonned;
        TimeDirection direction;
        command_queue.Promote(local_step, out added, out gonned, out direction);

        if (direction == TimeDirection.Forward)
            for (int i = 0; i < added.Count; i++)
            {
                commands_added.Add(added[i]);
            }
    }

    public ActorCommand CurrentCommand()
    {
        var cur = command_queue.CurrentState();
        if (cur != null)
            if (cur.StartStep == marked_as_finished_step)
                return null;
        return command_queue.CurrentState();
    }

    public void AddExternalCommandToQueueIfNeed(long local_step, ITimeline timeline)
    {
        if (external_command_one_buffer != null)
        {
            external_command_one_buffer.ShiftByStart(local_step);
            AddInternalCommand(external_command_one_buffer);
            external_command_one_buffer = null;
        }
    }

    // public MyList<ActorCommand> ActiveCommands()
    // {
    // 	return command_queue.ActiveStates();
    // }

    public void MarkAllCommandsAsFinished()
    {
        DropToCurrentState(Object().LocalStep());
        // var actives = command_queue.ActiveStates();
        // foreach (var cmd in actives)
        // {
        // 	MarkCommandAsFinished(cmd);
        // }
        MarkCommandAsFinished(LastActiveCommand());
    }

    public void Execute(long local_step, ITimeline timeline)
    {
        AddExternalCommandToQueueIfNeed(local_step, timeline);

        InternalPromote(local_step, timeline);
        //MyList<ActorCommand> actives = command_queue.ActiveStates();
        //Debug.Assert(actives.Count == 0 || actives.Count == 1);
        var current_command = command_queue.CurrentState();

        // if (actives.Count != 0)
        // {
        //  	Debug.Log("Actives:" + actor.Name() + " " + actives.Count);
        // }

        float camera_level = 0.0f;
        if (actor is Actor)
        {
            camera_level = (actor as Actor).CameraLevel;
        }

        if (current_command == null || current_command.StartStep == marked_as_finished_step)
        {
            if (actor.CurrentAnimatronicIsFinished())
            {
                var actor_as_actor = actor as Actor;
                bool is_croach_control =
                    actor_as_actor == null ? false : actor_as_actor.IsCroachControl();
                bool is_braced = actor_as_actor == null ? false : actor_as_actor.IsBraced();

                AnimationType atype = is_braced
                    ? AnimationType.BracedIdle
                    : is_croach_control
                        ? AnimationType.CroachIdle
                        : AnimationType.Idle;

                var idle_state = new IdleAnimatronic(
                    start_step: local_step,
                    pose: actor.CurrentReferencedPose(),
                    idle_animation: atype,
                    local_camera_pose: new Pose(
                        new Vector3(0, camera_level, 0),
                        Quaternion.identity
                    )
                );
                actor.SetNextAnimatronic(idle_state);
            }
            commands_added.Clear();
            return;
        }

        // if (commands_added != null)
        // {
        // 	foreach (var cmd in commands_added)
        // 	{
        // 		cmd.ExecuteFirstTime(actor, timeline);
        // 	}
        // }

        //foreach (var current in actives)
        if (current_command != null && !(current_command.StartStep == marked_as_finished_step))
        {
            var current = current_command;
            bool finished;
            if (commands_added != null && commands_added.Contains(current))
            {
                //Debug.Log("ExecuteFirstTime:" + actor.Name() + " " + current);
                finished = ExecuteFirstTime(current);
                commands_added.Remove(current);
            }
            else
                finished = current.Execute(actor, timeline);

            if (finished)
            {
                MarkCommandAsFinished(current);
            }
        }
        commands_added.Clear();
    }

    public ActionList<ActorCommand> GetCommandQueue()
    {
        return command_queue;
    }

    void MarkCommandAsFinished(ActorCommand command)
    {
        if (command == null || command.StartStep == marked_as_finished_step)
            return;

        command.StopHandler(this);

        //var current = command_queue.FirstActiveState();
        //Debug.Log("CommandBuffer.MarkCommandAsFinished:" + actor.Name() + " " + current);
        //if (current == null)
        //	return;

        //command_queue.MarkAsFinished(current);

        //current.SetFinishStep(Actor().LocalStep());
        //command_queue.ReAdd(current, Actor().LocalStep());

        //		Debug.Log("MarkCommandAsFinished " + command.GetType().Name);
        // var copy = command.Clone() as ActorCommand;
        // copy.SetFinishStep(Object().LocalStep());
        // command_queue.Replace(command, copy);

        // if (command.FinishStep == long.MaxValue)
        // {
        // 	var stub = new StubCommand(Object().LocalStep());
        // 	command_queue.Add(stub);
        // }
        marked_as_finished_step = command.StartStep;
    }

    ActorCommand LastActiveCommand()
    {
        return command_queue.CurrentState();
    }

    // AddInternalCommand дергается из того шага в котором команда исполняется первый раз
    public void AddInternalCommand(ActorCommand command)
    {
        var behaviour = this;
        var nactor = Object();

        if (Object().GetTimeline().IsPast())
        {
            var ntl = (Object().GetTimeline() as Timeline).Copy();
            ntl.DropTimelineToCurrentState();
            ntl.DropLastTimelineStep();
            var actor_name = Object().Name();
            nactor = ntl.GetObject(actor_name);
            behaviour = nactor.CommandBuffer();
            ntl.SetCurrent();
        }

        behaviour.MarkCommandAsFinished(LastActiveCommand());

        var list_of_removed = behaviour.command_queue.DropToCurrentState();

        foreach (var removed in list_of_removed)
        {
            removed.CancelHandler(behaviour);
        }

        behaviour.command_queue.Add(command);
    }

    bool ExecuteFirstTime(ActorCommand command)
    {
        if (command.Demasked() && Actor() is Actor)
        {
            Actor().Demask();
        }
        return command.ExecuteFirstTime(Actor(), Actor().GetTimeline());
    }

    public void AddExternalCommandAndApplyFromReversePass(ActorCommand command)
    {
        AddInternalCommand(command);
        ExecuteFirstTime(command);
    }

    public void AddExternalCommand(ActorCommand command)
    {
        AddInternalCommand(command);
    }

    public void ImportCommand(ActorCommand command)
    {
        command_queue.Add(command);
    }

    public CommandBufferBehaviour Copy(ObjectOfTimeline newactor)
    {
        CommandBufferBehaviour buf = new CommandBufferBehaviour(newactor);
        buf.command_queue = new ActionList<ActorCommand>(command_queue);
        buf._controlled_by_ai = _controlled_by_ai;
        buf.marked_as_finished_step = marked_as_finished_step;
        if (commands_added != null)
            buf.commands_added = new MyList<ActorCommand>(commands_added);
        //buf.last_executed_command = last_executed_command;
        return buf;
    }

    public void DropToCurrentState(long local_step)
    {
        //Debug.Log("CommandBuffer.DropToCurrentState:" + actor.Name() + " clean_buffer_on_drop:"+ clean_buffer_on_drop.ToString());
        if (CleanBufferOnDrop())
        {
            command_queue.DropToCurrentState();
        }

        //last_executed_command = command_queue.FirstActiveState();
    }

    public void DropToCurrentStateInverted(long local_step)
    {
        // Сброс буффера не требуется, потому что актор должен помнить поток комманд.
    }

    public bool IsEqual(CommandBufferBehaviour other)
    {
        if (other == null)
            return false;

        if (other._controlled_by_ai != _controlled_by_ai)
            return false;

        if (other.commands_added != null && commands_added != null)
        {
            if (other.commands_added.Count != commands_added.Count)
                return false;

            for (int i = 0; i < commands_added.Count; i++)
            {
                if (other.commands_added[i].IsEqual(commands_added[i]) == false)
                    return false;
            }
        }
        else if (other.commands_added != null || commands_added != null)
        {
            return false;
        }

        if (other.command_queue.IsEqual(command_queue) == false)
            return false;

        return true;
    }

    public Dictionary<string, object> ToTrent()
    {
        var dct = new Dictionary<string, object>();
        dct["controlled_by_ai"] = _controlled_by_ai;
        dct["command_queue"] = command_queue.ToTrent();
        if (commands_added != null)
        {
            var list = new MyList<object>();
            foreach (var cmd in commands_added)
            {
                list.Add(cmd.ToTrent());
            }
            dct["commands_added"] = list;
        }
        return dct;
    }

    // public static CommandBufferBehaviour CreateFromTrent(Dictionary<string, object> dct)
    // {
    // 	var controlled_by_ai = (bool)dct["controlled_by_ai"];
    // 	var command_queue = MultipleActionList<ActorCommand>.CreateFromTrent(dct["command_queue"] as Dictionary<string, object>);
    // 	var commands_added = new MyList<ActorCommand>();
    // 	if (dct.ContainsKey("commands_added"))
    // 	{
    // 		var list = dct["commands_added"] as MyList<object>;
    // 		foreach (var cmd in list)
    // 		{
    // 			commands_added.Add(ActorCommand.CreateFromTrent(cmd as Dictionary<string, object>));
    // 		}
    // 	}
    // 	var buf = new CommandBufferBehaviour(null);
    // 	buf._controlled_by_ai = controlled_by_ai;
    // 	buf.command_queue = command_queue;
    // 	buf.commands_added = commands_added;
    // 	return buf;
    // }

    public void FromTrent(Dictionary<string, object> dct)
    {
        _controlled_by_ai = (bool)dct["controlled_by_ai"];
        command_queue = ActionList<ActorCommand>.CreateFromTrent(
            dct["command_queue"] as Dictionary<string, object>
        );
        if (dct.ContainsKey("commands_added"))
        {
            var list = dct["commands_added"] as MyList<object>;
            commands_added = new MyList<ActorCommand>();
            foreach (var cmd in list)
            {
                commands_added.Add(
                    ActorCommand.CreateFromTrent(cmd as Dictionary<string, object>) as ActorCommand
                );
            }
        }
    }
}
