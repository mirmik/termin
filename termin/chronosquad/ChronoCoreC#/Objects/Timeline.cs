using System.Collections;
using System.Collections.Generic;
using System;
using System.Collections.Concurrent;
using System.Threading.Tasks;

// using for StopWatch
using System.Diagnostics;

// IJobParallelFor
//using Unity.Jobs;

// native container
//using Unity.Collections;

#if UNITY_64
using Debug = UnityEngine.Debug;
using UnityEngine;
#endif

public enum ParadoxStatus
{
    NoParadox,
    ParadoxDetected
}

public class EntrancePoint
{
    public string parent_timeline_key;
    public string child_timeline_key;
    public long parent_step;
    public long child_step;

    public EntrancePoint() { }
}

public class Timeline : ITimeline
{
    public PresentState present;
    string _name = "";
    public bool IsTimeSpirit { get; set; } = false;
    NetworkMap _network_map;
    MyDictionary<string, ObjectOfTimeline> _memorized_objects =
        new MyDictionary<string, ObjectOfTimeline>();
    public MyList<ObjectOfTimeline> _memorized_objects_list = new MyList<ObjectOfTimeline>();
    MyDictionary<long, ObjectOfTimeline> _memorized_objects_hashes =
        new MyDictionary<long, ObjectOfTimeline>();
    MyDictionary<string, ObjectOfTimeline> _next_pass_list =
        new MyDictionary<string, ObjectOfTimeline>();
    Int64 _event_count = 0;
    Int64 _last_positive_timeline_step = 0;
    Int64 _last_negative_timeline_step = 0;
    Int64 _minimal_step = 0;
    Int64 _maximal_step = Int64.MaxValue;
    ChronoSphere chronosphere;
    MyList<Timeline> _syncronized_timelines = new MyList<Timeline>();
    Int64 _current_step = 0;
    float _current_time = 0;
    MyList<ObjectOfTimeline> _heroes = new MyList<ObjectOfTimeline>();
    MyList<ObjectOfTimeline> _enemies = new MyList<ObjectOfTimeline>();
    bool _is_reversed_pass = false;
    bool _start_phase_invoked = false;
    EventLine<ITimeline> scripts = new EventLine<ITimeline>(true);
    public EventLine<ITimeline> global_events = new EventLine<ITimeline>(true);
    public EventLine<ITimeline> nondropable_global_events = new EventLine<ITimeline>(true);
    EventLine<ITimeline> reversed_global_events = new EventLine<ITimeline>(true);
    public EventLine<ITimeline> reversed_nondropable_global_events = new EventLine<ITimeline>(true);
    MultipleActionList<SpeachObject> speach_objects = new MultipleActionList<SpeachObject>(true);
    public NarativeState NarativeState = new NarativeState();
    OnScreenTextModel _onscreen_text_model = new OnScreenTextModel();
    TimeDirection _last_time_direction = TimeDirection.Forward;
    public EntrancePoint _primary_entrance_point;
    public MyList<EntrancePoint> _entrance_point = new MyList<EntrancePoint>();
    public MyList<EntrancePoint> ChildTimelines = new MyList<EntrancePoint>();
    public EntrancePoint PrimaryEntrancePoint => _primary_entrance_point;
    public bool step_evaluation_flag = false;
    MyList<Action> _after_step_update_actions = new MyList<Action>();
    MyList<Action> _after_promotion_update_actions = new MyList<Action>();
    public MyList<Trigger> Triggers = new MyList<Trigger>();
    public Dictionary<long, Trigger> TriggersDict = new Dictionary<long, Trigger>();

    public void AddTrigger(Trigger trigger)
    {
        Triggers.Add(trigger);
        TriggersDict.Add(trigger.HashCode(), trigger);
    }

    public Trigger GetTrigger(long hash)
    {
        return TriggersDict[hash];
    }

    public void CheckTriggerPhase()
    {
        foreach (var trigger in Triggers)
        {
            trigger.CheckTrigger(this);
        }
    }

    // public void AddAspect(string name, TimelineAspectManager aspect)
    // {
    // 	_aspects.Add(name, aspect);
    // 	aspect.SetName(name);
    // }

    // public TimelineAspectManager GetAspect(string name)
    // {
    // 	if (_aspects.ContainsKey(name))
    // 		return _aspects[name];
    // 	return null;
    // }


    public string info()
    {
        string report = "";
        report += "Timeline: " + _name + "\n";
        report += "Current step: " + _current_step + "\n";
        report += "Last positive step: " + _last_positive_timeline_step + "\n";
        report += "Last negative step: " + _last_negative_timeline_step + "\n";
        report += "Minimal step: " + _minimal_step + "\n";
        report += "Maximal step: " + _maximal_step + "\n";
        report += "Reversed pass: " + _is_reversed_pass + "\n";
        report += "Event count: " + _event_count + "\n";
        report += "Global events: " + global_events.CountOfCards() + "\n";
        report += "Non dropable global events: " + nondropable_global_events.CountOfCards() + "\n";
        report += "Heroes: " + _heroes.Count + "\n";
        report += "Enemies: " + _enemies.Count + "\n";
        report += "Objects: " + _memorized_objects.Count + "\n";
        return report;
    }

    TimeDirection PassDirection =>
        _is_reversed_pass ? TimeDirection.Backward : TimeDirection.Forward;

    public MyList<SpeachObject> ActiveSpeaches()
    {
        return speach_objects.ActiveStates();
    }

    public void AddAfterStepUpdateAction(Action action)
    {
        _after_step_update_actions.Add(action);
    }

    public void AddAfterPromotionUpdateAction(Action action)
    {
        _after_promotion_update_actions.Add(action);
    }

    public bool IsStepEvaluationPhase()
    {
        return step_evaluation_flag;
    }

    public void SetPrimaryEntrancePoint(EntrancePoint ep)
    {
        _primary_entrance_point = ep;
        _entrance_point[0] = ep;
    }

    public void AddEntrancePoint(EntrancePoint ep)
    {
        _entrance_point.Add(ep);
    }

    public void RemoveEntrancePoint(EntrancePoint ep)
    {
        _entrance_point.Remove(ep);
    }

    public void AddChildEntrancePoint(EntrancePoint tl)
    {
        ChildTimelines.Add(tl);
    }

    public void RemoveChildEntrancePoint(EntrancePoint tl)
    {
        ChildTimelines.Remove(tl);
    }

    // public void SortChildTimelines()
    // {
    // 	ChildTimelines.Sort((x, y) => x.parent_step.CompareTo(y.parent_step));
    // }

    public Timeline(ChronoSphere ch) : this()
    {
        this.chronosphere = ch;
    }

    public Timeline(string name) : this()
    {
        _name = name;
    }

    public Timeline()
    {
        _primary_entrance_point = new EntrancePoint();
        _entrance_point.Add(_primary_entrance_point);
        _network_map = new NetworkMap(this);
        present = new PresentState(this);
    }

    public long PrimaryEntranceStep()
    {
        return _entrance_point[0].parent_step;
    }

    public void AddToNextPassList(ObjectOfTimeline nextobj)
    {
        string name = nextobj.Name();
        if (_next_pass_list.ContainsKey(name))
            return;
        _next_pass_list.Add(name, nextobj);
    }

    public MyDictionary<string, ObjectOfTimeline> NextPassList()
    {
        return _next_pass_list;
    }

    public void SetMinimalStep(Int64 step)
    {
        _minimal_step = step;
    }

    public void SetMaximalStep(Int64 step)
    {
        _maximal_step = step;
    }

    public Int64 MinimalStep()
    {
        return _minimal_step;
    }

    public Int64 MaximalStep()
    {
        return _maximal_step;
    }

    public void StartPhase()
    {
        foreach (var obj in _memorized_objects.Values)
        {
            obj.StartPhase();
        }
        _start_phase_invoked = true;
    }

    public ChronoSphere GetChronoSphere()
    {
        return chronosphere;
    }

    public void SetCurrentTimeline()
    {
        if (chronosphere != null)
            chronosphere.set_current_timeline(this);
    }

    public NetworkMap GetNetworkMap()
    {
        return _network_map;
    }

    public long CurrentToPresentDifferece()
    {
        if (!IsReversedPass())
            return LastPositiveTimelineStep() - CurrentStep();
        else
            return CurrentStep() - LastNegativeTimelineStep();
    }

    public float CurrentToPresentDiffereceSeconds()
    {
        return CurrentToPresentDifferece() / Utility.GAME_GLOBAL_FREQUENCY;
    }

    void CopyTimelineStateWithouObjects(Timeline tl)
    {
        chronosphere = tl.chronosphere;
        _last_positive_timeline_step = tl._last_positive_timeline_step;
        _last_negative_timeline_step = tl._last_negative_timeline_step;
        _event_count = tl._event_count;
        _minimal_step = tl._minimal_step;
        _maximal_step = tl._maximal_step;
        _current_step = tl._current_step;
        _is_reversed_pass = tl._is_reversed_pass;
        _last_time_direction = tl._last_time_direction;

        Triggers = new MyList<Trigger>();
        TriggersDict = new Dictionary<long, Trigger>();
        for (int i = 0; i < tl.Triggers.Count; i++)
        {
            var trigger = tl.Triggers[i].Copy();
            Triggers.Add(trigger);
            TriggersDict.Add(trigger.HashCode(), trigger);
        }

        global_events = new EventLine<ITimeline>(tl.global_events);
        nondropable_global_events = new EventLine<ITimeline>(tl.nondropable_global_events);
    }

    public EventLine<ITimeline> NonDropableGlobalEvents() => nondropable_global_events;

    void CopyTimelineObjects(Timeline tl)
    {
        //CopyAspects(tl);

        foreach (var kv in tl._memorized_objects)
        {
            var copy = kv.Value.Copy(this);
            AddObject(kv.Key, copy);
        }

        foreach (var kv in tl._next_pass_list)
        {
            var copy = kv.Value.Copy(this);
            AddToNextPassList(copy);
        }
        InitHeroesArray();
    }

    // public void CopyAspects(ITimeline tl)
    // {
    // 	foreach (var kv in tl._aspects)
    // 	{
    // 		var copy = kv.Value.Copy(this);
    // 		AddAspect(kv.Key, copy);
    // 	}
    // }

    public void InitActorLinks(Timeline tl)
    {
        foreach (var kv in tl._memorized_objects)
        {
            var copy = kv.Value;
            if (copy is Actor)
                ((Actor)copy).InitActorLinks();
        }
    }

    public void FindNearestObject(Vector3 globpos, float radius, Action<ObjectOfTimeline> action)
    {
        foreach (var obj in _memorized_objects.Values)
        {
            if (obj is Actor)
            {
                var actor = obj as Actor;
                if (actor.IsDead || actor.IsPreDead)
                    continue;
            }

            var pos = obj.GlobalPose().position;
            if (Vector3.Distance(globpos, pos) < radius)
                action(obj);
        }
    }

    public void SetupEntrancePointForCopy(Timeline copy)
    {
        var entrance_point = new EntrancePoint();
        entrance_point.parent_timeline_key = this.Name();
        entrance_point.child_timeline_key = copy.Name();
        entrance_point.parent_step = this.CurrentStep();
        entrance_point.child_step = copy.CurrentStep();

        this.AddChildEntrancePoint(entrance_point);
        copy.SetPrimaryEntrancePoint(entrance_point);
    }

    public Timeline Copy(long offset = 0, bool reverse = false)
    {
        Timeline copy = new Timeline();
        copy.CopyTimelineStateWithouObjects(this);
        copy.CopyTimelineObjects(this);
        copy.present = new PresentState(copy, present);
        copy.ReleaseNextPassObjects();
        this.InitActorLinks(this);
        copy.SetName("Timeline" + UniqueIdGenerator.GetNextId());

        copy.StartPhase();
        var network_map = copy.GetNetworkMap();
        network_map.MakeConnectionGraphByPoints();

        copy.Promote(this.CurrentStep() + offset);
        SetupEntrancePointForCopy(copy);

        if (reverse)
            copy.SetReversedPass(!IsReversedPass());

        return copy;
    }

    public void ReleaseNextPassObjects()
    {
        foreach (var o in _next_pass_list)
        {
            AddObject(o.Value);
        }
        _next_pass_list.Clear();
    }

    public void DropLastTimelineStep(TimeDirection direction)
    {
        if (direction == TimeDirection.Forward)
            _last_positive_timeline_step = _current_step;
        else
            _last_negative_timeline_step = _current_step;
    }

    public void DropLastTimelineStep()
    {
        if (IsReversedPass())
            _last_negative_timeline_step = _current_step;
        else
            _last_positive_timeline_step = _current_step;
    }

    public void DropMinMaxTimelineStep()
    {
        if (IsReversedPass())
        {
            _maximal_step = _current_step;
            _minimal_step = chronosphere.GlobalMinStep;
        }
        else
        {
            _minimal_step = _current_step;
            _maximal_step = chronosphere.GlobalMaxStep;
        }
    }

    public bool IsReversedPass()
    {
        return _is_reversed_pass;
    }

    public void SetReversedPass(bool value)
    {
        _is_reversed_pass = value;
    }

    public void SetName(string name)
    {
        _name = name;
    }

    public string Name() => _name;

    public MyList<ObjectOfTimeline> Heroes()
    {
        return _heroes;
    }

    public MyList<ObjectOfTimeline> Enemies()
    {
        return _enemies;
    }

    public CanSee IsCanSee(int from, int to)
    {
        return present.IsCanSee(from, to);
    }

    public void SetChronosphere(ChronoSphere ch)
    {
        chronosphere = ch;
    }

    public Int64 LastPositiveTimelineStep()
    {
        return _last_positive_timeline_step;
    }

    public Actor CreateGuard(string name)
    {
        var obj = new Actor(name);
        this.AddObject(obj);
        return obj;
    }

    public T CreateObject<T>(string name) where T : ObjectOfTimeline, new()
    {
        var obj = new T();
        obj.SetName(name);
        this.AddObject(obj);
        return obj;
    }

    public Int64 LastNegativeTimelineStep()
    {
        return _last_negative_timeline_step;
    }

    public void SetCurrent()
    {
        chronosphere.set_current_timeline(this);
    }

    public bool IsPresent()
    {
        if (IsReversedPass())
            return CurrentStep() == _last_negative_timeline_step;
        else
            return CurrentStep() == _last_positive_timeline_step;
    }

    public bool InCurrentGroup()
    {
        return chronosphere.CurrentGroup.Contains(this);
    }

    public bool IsCurrent()
    {
        return chronosphere.CurrentTimeline() == this;
    }

    public bool IsPast()
    {
        return !IsPresent();
    }

    public MyDictionary<string, ObjectOfTimeline> Objects()
    {
        return _memorized_objects;
    }

    public void InitHeroesArray()
    {
        _heroes = new MyList<ObjectOfTimeline>();
        foreach (var obj in _memorized_objects.Values)
        {
            if (obj is ObjectOfTimeline)
            {
                var actor = obj as ObjectOfTimeline;
                if (actor.IsHero())
                    _heroes.Add(actor);
            }
        }

        _enemies = new MyList<ObjectOfTimeline>();
        foreach (var obj in _memorized_objects.Values)
        {
            if (obj is ObjectOfTimeline)
            {
                var actor = obj as ObjectOfTimeline;
                if (!actor.IsHero())
                    _enemies.Add(actor);
            }
        }
    }

    public ChronoSphere GetChronosphere()
    {
        return chronosphere;
    }

    public void DropTimelineToCurrentState()
    {
        if (IsPast())
        {
            foreach (var pair in _memorized_objects)
            {
                var actor = pair.Value;
                if (actor.IsReversed() == IsReversedPass())
                    actor.DropToCurrentState();
            }

            _last_positive_timeline_step = CurrentStep();
            _last_negative_timeline_step = CurrentStep();

            if (!IsReversedPass())
            {
                global_events.DropToCurrentState();
            }
            else
            {
                global_events.DropToCurrentStateInverted();
            }
            // if (chronosphere != null)
            // 	chronosphere.SendMessage(
            // 		"Произведено редактирование временной линии",
            // 		CurrentStep()
            // 	);
        }
    }

    public EventLine<ITimeline> GlobalEvents()
    {
        return global_events;
    }

    public double last_timeline_time()
    {
        return _last_positive_timeline_step / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public int CountOfCards()
    {
        int count = 0;
        foreach (var obj in _memorized_objects.Values)
        {
            count += obj.CountOfCards();
        }
        count += global_events.CountOfCards();
        return count;
    }

    public void RemoveObject(ObjectOfTimeline obj)
    {
        _memorized_objects.Remove(obj.Name());
        _memorized_objects_list.Remove(obj);
        _memorized_objects_hashes.Remove(obj.ObjectId().hash);

        present.RemoveActiveObject(obj);
        if (GetChronosphere() != null)
            GetChronosphere().InvokeOnObjectRemoved(obj);
    }

    public void AddObject(ObjectOfTimeline obj)
    {
        AddObject(obj.Name(), obj);
    }

    public bool HasObject(string name)
    {
        return _memorized_objects.ContainsKey(name);
    }

    public bool HasObject(ObjectId name)
    {
        return _memorized_objects_hashes.ContainsKey(name.hash);
    }

    public void AddObject(string name, ObjectOfTimeline obj)
    {
        obj.SetName(name);
        if (_memorized_objects.ContainsKey(name))
        {
            if (_memorized_objects[name] == obj)
                return;
            else
            {
                Debug.Log(
                    "Timeline already contains object with name "
                        + name
                        + "and it is not equal to new object"
                );
                return;
            }
        }

        _memorized_objects.Add(name, obj);
        _memorized_objects_list.Add(obj);
        _memorized_objects_hashes.Add(Utility.StringHash(name), obj);

        if (obj.IsHero())
            _heroes.Add(obj);
        else
            _enemies.Add(obj);

        obj.SetTimeline(this);

        if (GetChronosphere() != null)
            GetChronosphere().InvokeOnObjectAdded(obj);

        obj._timeline_index = _memorized_objects.Count - 1;

        present.AddActiveObject(obj);
    }

    public MyDictionary<string, ObjectOfTimeline> objects()
    {
        return _memorized_objects;
    }

    public Pose GetFrame(ObjectId frame_name)
    {
        if (frame_name.hash == 0)
            return Pose.Identity;

        var obj = GetObject(frame_name);

        if (obj == null)
        {
            throw new Exception("Object with name not found: " + frame_name.name);
        }

        return obj.GlobalPose();
    }

    public ReferencedScrew GetVelocityScrew(long frame_name)
    {
        if (frame_name == 0)
            return new ReferencedScrew();

        var obj = GetObject(frame_name);
        return obj.GetReferencedVelocity();
    }

    public ReferencedScrew GetVelocityScrew(ObjectId frame_name)
    {
        if (frame_name.hash == 0)
            return new ReferencedScrew();

        var obj = GetObject(frame_name);
        return obj.GetReferencedVelocity();
    }

    public bool ContainsNonDropableEvent(long hash)
    {
        return nondropable_global_events.ContainsHash(hash);
    }

    public long CurrentStep()
    {
        return _current_step;
    }

    public float CurrentTime() => _current_time;

    public void AddEvent(EventCard<ITimeline> ev)
    {
        global_events.Add(ev);
    }

    public void AddNonDropableEvent(EventCard<ITimeline> ev)
    {
        nondropable_global_events.Add(ev);
    }

    public string name()
    {
        return _name;
    }

    public MultipleActionList<EventCard<ITimeline>> Events()
    {
        return global_events.MyList;
    }

    public MyList<EventCard<ITimeline>> ActiveEvents()
    {
        return global_events.MyList.ActiveStates();
    }

    // public MyList<EventCard<Timeline>> EventsAsList()
    // {
    // 	return global_events.MyList.AsList();
    // }

    public double current_time()
    {
        return CurrentStep() / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public void drop_real_time_to_moment(Int64 moment, bool with_syncronization = false)
    {
        _last_positive_timeline_step = moment;
    }

    public void drop_real_time_to_CurrentStep()
    {
        drop_real_time_to_moment(this.CurrentStep());
    }

    // public void add_syncronized_timeline(ITimeline tl)
    // {
    // 	_syncronized_timelines.Add(tl);
    // }

    public void AddMessage(string text, long start_step, long finish_step)
    {
        _onscreen_text_model.AddMessage(text, start_step, finish_step);
    }

    public void AddMessage(string text)
    {
        _onscreen_text_model.AddMessage(text, CurrentStep(), CurrentStep() + 2000);
    }

    public OnScreenTextModel OnScreenText()
    {
        return _onscreen_text_model;
    }

    public void AfterStepPhase()
    {
        foreach (var action in _after_step_update_actions)
        {
            action();
        }
        _after_step_update_actions.Clear();
    }

    public void UpdateLocalStepPhase(long curstep)
    {
        foreach (var actor in _memorized_objects_list)
        {
            actor.PreevaluateLocalStep(curstep);
        }
    }

    public void ScriptPhase()
    {
        scripts.Promote(CurrentStep(), this);
        var actives = scripts.MyList.ActiveStates();

        foreach (var script in actives)
        {
            if (script == null)
                continue;

            var script_obj = script as ControllerScript;
            script_obj.Execute(this);
        }
    }

    private void do_step(TimeDirection direction)
    {
        if (direction == TimeDirection.Forward)
            increment_step();
        else
            decrement_step();
        step_evaluation_flag = true;

        long curstep = CurrentStep();

        UpdateLocalStepPhase(curstep);
        if (!IsPast() && PassDirection == direction)
        {
            //EvaluateDistanceMatrix();
            GameCore.UpdateTimelineSightMatrix(this);
            PlanningPhase(CurrentStep(), direction);
        }

        present.ActionPhase(curstep);
        CheckTriggerPhase();
        TestSeePhase();

        ScriptPhase();
        AfterStepPhase();

        _onscreen_text_model.Promote(curstep);
        _last_time_direction = direction;

        step_evaluation_flag = false;
    }

    // private void positive_step()
    // {
    // 	do_step(TimeDirection.Forward);
    // }

    // private void negative_step()
    // {
    // 	do_step(TimeDirection.Backward);
    // }

    public MyList<ObjectOfTimeline> ObjectList()
    {
        return _memorized_objects_list;
    }

    public void DeleteVariant(ObjectOfTimeline obj)
    {
        var current_timeline_step = obj.LocalStep();
        var object_start_timeline_step = obj.ObjectStartTimelineStep();
        Debug.Log(
            "Пересчитываю вариант: start: "
                + object_start_timeline_step
                + " current: "
                + current_timeline_step
        );
        this.Promote(object_start_timeline_step);
        this.RemoveObject(obj);
        obj.OnRemove();
        this.DropTimelineToCurrentState();
        this.Promote(current_timeline_step);
    }

    public void promote_steps(Int64 n, bool with_syncronization = false)
    {
        if (_start_phase_invoked == false)
        {
            StartPhase();
        }

        TimeDirection direction;
        if (n > 0)
        {
            direction = TimeDirection.Forward;
        }
        else
        {
            direction = TimeDirection.Backward;
            n = -n;
        }

        for (Int64 i = 0; i < n; i++)
            do_step(direction);

        if (with_syncronization)
            foreach (var tl in _syncronized_timelines)
                tl.promote_to_steps(CurrentStep());

        AfterPromotionPhase();
    }

    void AfterPromotionPhase()
    {
        foreach (var action in _after_promotion_update_actions)
        {
            action();
        }
        _after_promotion_update_actions.Clear();
    }

    public void TestSeePhase()
    {
        foreach (var actor in _memorized_objects_list)
        {
            actor.CleanFlags();
        }

        foreach (var actor in _memorized_objects_list)
        {
            actor.TestSeePhase();
        }
    }

    public void PlanningPhase(Int64 curstep, TimeDirection direction)
    {
        foreach (var actor in _memorized_objects_list)
        {
            bool reversed_pass = IsReversedPass();
            bool reversed_actor = actor.IsReversed();
            if (reversed_pass != reversed_actor)
                continue;
            actor.Execute(curstep);
        }
    }

    public void FastPromote(Int64 steps)
    {
        _current_step = steps;

        foreach (var actor in _memorized_objects_list)
            actor.Promote(steps);

        global_events.Promote(steps, this);
        nondropable_global_events.Promote(steps, this);
    }

    public void RemoveNonDropableEvent(long hash)
    {
        nondropable_global_events.MyList.RemoveByHashCode(hash);
    }

    public Int64 events_count()
    {
        return _event_count;
    }

    public void promote_to_steps(Int64 newsteps, bool with_syncronization = false)
    {
        Int64 delta = newsteps - CurrentStep();
        promote_steps(delta);
    }

    public void Promote2(long steps)
    {
        promote_to_steps(steps);
    }

    public void Promote(long steps)
    {
        var time = steps / Utility.GAME_GLOBAL_FREQUENCY;
        promote_to_steps(steps);
        _current_time = (float)time;
    }

    public void PromoteToTime(double time)
    {
        int target_step = (int)(time * Utility.GAME_GLOBAL_FREQUENCY);
        promote_to_steps(target_step);
        _current_time = (float)time;
    }

    public void increment_step()
    {
        _current_step += 1;
        if (_last_positive_timeline_step < _current_step)
            _last_positive_timeline_step = _current_step;
    }

    public void decrement_step()
    {
        _current_step -= 1;
        if (_last_negative_timeline_step > _current_step)
            _last_negative_timeline_step = _current_step;
    }

    public ObjectOfTimeline GetObject(string name)
    {
        var hash = Utility.StringHash(name);
        return _memorized_objects_hashes[hash];
    }

    public ObjectOfTimeline GetObject(ObjectId name)
    {
        var hash = name.hash;
        return _memorized_objects_hashes[hash];
    }

    public ObjectOfTimeline GetObject(long name)
    {
        return _memorized_objects_hashes[name];
    }

    public ObjectOfTimeline TryGetObject(string name)
    {
        if (name == null)
            return null;

        if (!_memorized_objects.ContainsKey(name))
        {
            return null;
        }

        return _memorized_objects[name];
    }

    public void PromoteDelta(double delta)
    {
        PromoteToTime(_current_time + delta);
    }

    public void AddDialogue(DialogueGraph dialogue, long step)
    {
        NarativeState.AddDialogue(dialogue, step);
    }

    public Actor GetActor(string name)
    {
        if (_next_pass_list.ContainsKey(name))
        {
            return _next_pass_list[name] as Actor;
        }

        if (!_memorized_objects.ContainsKey(name))
        {
            Debug.Log("Timeline not contains object '" + name + "'");
        }

        return _memorized_objects[name] as Actor;
    }

    public Actor GetActor(ObjectId name)
    {
        if (_next_pass_list.ContainsKey(name.name))
        {
            return _next_pass_list[name.name] as Actor;
        }

        if (!_memorized_objects.ContainsKey(name.name))
        {
            Debug.Log("Timeline not contains object '" + name.name + "'");
        }

        return _memorized_objects[name.name] as Actor;
    }

    public Actor TryGetActor(string name)
    {
        if (name == null)
            return null;

        if (!_memorized_objects.ContainsKey(name))
        {
            return null;
        }

        return _memorized_objects[name] as Actor;
    }

    public bool IsEqual(Timeline other)
    {
        if (_memorized_objects.Count != other._memorized_objects.Count)
        {
            Debug.Log("Different count of memorized objects");
            return false;
        }

        if (_next_pass_list.Count != other._next_pass_list.Count)
        {
            Debug.Log("Different count of next pass list");
            return false;
        }

        if (_current_step != other._current_step)
        {
            Debug.Log("Different current step");
            return false;
        }

        // if (!global_events.IsEqual(other.global_events))
        // {
        // 	Debug.Log("Different global events");
        // 	return false;
        // }

        // if (!nondropable_global_events.IsEqual(other.nondropable_global_events))
        // {
        // 	Debug.Log("Different non dropable global events");
        // 	return false;
        // }

        foreach (var kv in _memorized_objects)
        {
            if (!other._memorized_objects.ContainsKey(kv.Key))
            {
                Debug.Log("Different memorized objects keys");
                return false;
            }

            if (!kv.Value.IsEqual(other._memorized_objects[kv.Key]))
            {
                Debug.Log("Different memorized object " + kv.Key);
                return false;
            }
        }

        foreach (var kv in _next_pass_list)
        {
            if (!other._next_pass_list.ContainsKey(kv.Key))
            {
                Debug.Log("Different next pass list keys");
                return false;
            }

            if (!kv.Value.IsEqual(other._next_pass_list[kv.Key]))
            {
                Debug.Log("Different next pass list object" + kv.Key);
                return false;
            }
        }

        return true;
    }

    public bool IsEqual_Return(Timeline other, out MyList<string> paradoxed_objects)
    {
        paradoxed_objects = new MyList<string>();

        if (_memorized_objects.Count != other._memorized_objects.Count)
        {
            Debug.Log("Different count of memorized objects");
            return false;
        }

        if (_next_pass_list.Count != other._next_pass_list.Count)
        {
            Debug.Log("Different count of next pass list");
            return false;
        }

        if (_current_step != other._current_step)
        {
            Debug.Log("Different current step");
            return false;
        }

        if (!global_events.IsEqual(other.global_events))
        {
            Debug.Log("Different global events");
            return false;
        }

        if (!nondropable_global_events.IsEqual(other.nondropable_global_events))
        {
            Debug.Log("Different non dropable global events");
            return false;
        }

        foreach (var kv in _memorized_objects)
        {
            if (!other._memorized_objects.ContainsKey(kv.Key))
            {
                paradoxed_objects.Add(kv.Key);
                Debug.Log("Different memorized objects keys");
            }

            if (!kv.Value.IsEqual(other._memorized_objects[kv.Key]))
            {
                paradoxed_objects.Add(kv.Key);
                Debug.Log("Different memorized object " + kv.Key);
            }
        }

        foreach (var kv in _next_pass_list)
        {
            if (!other._next_pass_list.ContainsKey(kv.Key))
            {
                Debug.Log("Different next pass list keys");
                return false;
            }

            if (!kv.Value.IsEqual(other._next_pass_list[kv.Key]))
            {
                Debug.Log("Different next pass list object" + kv.Key);
                return false;
            }
        }

        return true;
    }

    public bool IsEqual_Return_Quite(Timeline other, out MyList<string> paradoxed_objects)
    {
        paradoxed_objects = new MyList<string>();

        if (_memorized_objects.Count != other._memorized_objects.Count) { }

        if (_next_pass_list.Count != other._next_pass_list.Count) { }

        if (_current_step != other._current_step) { }

        if (!global_events.IsEqual(other.global_events)) { }

        if (!nondropable_global_events.IsEqual(other.nondropable_global_events)) { }

        foreach (var kv in _memorized_objects)
        {
            if (!other._memorized_objects.ContainsKey(kv.Key))
            {
                paradoxed_objects.Add(kv.Key);
            }

            if (!kv.Value.IsEqual(other._memorized_objects[kv.Key]))
            {
                paradoxed_objects.Add(kv.Key);
            }
        }

        foreach (var kv in _next_pass_list)
        {
            if (!other._next_pass_list.ContainsKey(kv.Key))
            {
                paradoxed_objects.Add(kv.Key);
            }

            if (!kv.Value.IsEqual(other._next_pass_list[kv.Key]))
            {
                paradoxed_objects.Add(kv.Key);
            }
        }

        return paradoxed_objects.Count == 0;
    }

    public ParadoxStatus CheckTimeParadox()
    {
        Timeline copy = Copy();
        copy.Promote(0 * (long)Utility.GAME_GLOBAL_FREQUENCY);
        copy.DropTimelineToCurrentState();
        copy.Promote(CurrentStep());

        bool is_equal = copy.IsEqual(this);
        if (!is_equal)
        {
            Debug.Log("Time paradox detected");
        }

        return is_equal ? ParadoxStatus.NoParadox : ParadoxStatus.ParadoxDetected;
    }

    public ParadoxStatus CheckTimeParadox_Return()
    {
        Timeline copy = Copy();
        copy.Promote(0 * (long)Utility.GAME_GLOBAL_FREQUENCY);
        copy.DropTimelineToCurrentState();
        copy.Promote(CurrentStep());

        MyList<string> paradoxed_objects;
        bool is_equal = copy.IsEqual_Return(this, out paradoxed_objects);
        if (!is_equal)
        {
            Debug.Log("Time paradox detected");
        }

        return is_equal ? ParadoxStatus.NoParadox : ParadoxStatus.ParadoxDetected;
    }

    public void MarkParadoxes()
    {
        Debug.Log("MarkParadoxes");

        Timeline copy = Copy();
        copy.Promote(0 * (long)Utility.GAME_GLOBAL_FREQUENCY);
        copy.DropTimelineToCurrentState();
        copy.Promote(CurrentStep());

        MyList<string> paradoxed_objects;
        bool is_equal = copy.IsEqual_Return_Quite(this, out paradoxed_objects);
        if (!is_equal)
        {
            Debug.Log("Time paradox detected");
            foreach (var obj in paradoxed_objects)
            {
                if (_memorized_objects.ContainsKey(obj))
                    _memorized_objects[obj].SetTimeParadox(true);
                if (_next_pass_list.ContainsKey(obj))
                    _next_pass_list[obj].SetTimeParadox(true);
            }
        }
    }

    public void FromTrent(Dictionary<string, object> dict)
    {
        _name = (string)dict["name"];
        _memorized_objects = new MyDictionary<string, ObjectOfTimeline>();
        foreach (var kv in (MyDictionary<string, object>)dict["memorized_objects"])
        {
            var obj = ObjectOfTimeline.CreateFromTrent((Dictionary<string, object>)kv.Value);
            _memorized_objects[kv.Key] = obj;
        }
        _next_pass_list = new MyDictionary<string, ObjectOfTimeline>();
        foreach (var kv in (MyDictionary<string, object>)dict["next_pass_list"])
        {
            var obj = ObjectOfTimeline.CreateFromTrent((Dictionary<string, object>)kv.Value);
            _next_pass_list[kv.Key] = obj;
        }
        _event_count = (Int64)dict["event_count"];
        _last_positive_timeline_step = (Int64)dict["last_positive_timeline_step"];
        _last_negative_timeline_step = (Int64)dict["last_negative_timeline_step"];
        _minimal_step = (Int64)dict["minimal_step"];
        _maximal_step = (Int64)dict["maximal_step"];
        _current_step = (Int64)dict["current_step"];
        _is_reversed_pass = (bool)dict["is_reversed_pass"];
        global_events = new EventLine<ITimeline>(true);
        global_events.FromTrent((MyDictionary<string, object>)dict["global_events"]);
        nondropable_global_events = new EventLine<ITimeline>(true);
        nondropable_global_events.FromTrent(
            (MyDictionary<string, object>)dict["nondropable_global_events"]
        );
        _last_time_direction = (TimeDirection)
            Enum.Parse(typeof(TimeDirection), (string)dict["last_time_direction"]);
    }

    public Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["name"] = _name;
        dict["memorized_objects"] = new Dictionary<string, object>();
        foreach (var kv in _memorized_objects)
        {
            ((MyDictionary<string, object>)dict["memorized_objects"])[kv.Key] = kv.Value.ToTrent();
        }
        dict["next_pass_list"] = new Dictionary<string, object>();
        foreach (var kv in _next_pass_list)
        {
            ((MyDictionary<string, object>)dict["next_pass_list"])[kv.Key] = kv.Value.ToTrent();
        }
        dict["event_count"] = _event_count;
        dict["last_positive_timeline_step"] = _last_positive_timeline_step;
        dict["last_negative_timeline_step"] = _last_negative_timeline_step;
        dict["minimal_step"] = _minimal_step;
        dict["maximal_step"] = _maximal_step;
        dict["current_step"] = _current_step;
        dict["is_reversed_pass"] = _is_reversed_pass;
        dict["global_events"] = global_events.ToTrent();
        dict["nondropable_global_events"] = nondropable_global_events.ToTrent();
        dict["last_time_direction"] = _last_time_direction.ToString();
        return dict;
    }

    static public Timeline CreateFromTrent(Dictionary<string, object> dict)
    {
        Timeline tl = new Timeline();
        tl.FromTrent(dict);
        return tl;
    }
}



// struct PreevaluatedObjectState
// {
// 	public Vector3 _preevaluated_torso_position;
// 	public Vector2 _preevaluated_global_position_xz;
// 	public Pose _preevaluated_global_pose;
// 	public Vector2 _preevaluated_global_direction_xz;
// 	public Vector3 _preevaluated_global_camera_position;
// 	public Vector2 _preevaluated_global_camera_direction_xz;
// }

// // #if !UNITY_64
// // interface IJobParallelFor {}

// // public class NativeArray<T>
// // {
// // 	public T[] values = new T[10];
// // 	public T this[int index] { get { return values[index]; } set { values[index] = value; } }
// // 	public int Length { get; set; }
// // }
// // #endif



// struct PreevaluationJob: IJobParallelFor
// {
// 	public NativeArray<PreevaluatedObjectState> values;
// 	public Timeline timeline;

// 	public PreevaluationJob(int length, Timeline timeline)
// 	{
// 		values = new NativeArray<PreevaluatedObjectState>(
// 			length,
// 			Allocator.Persistent);
// 		this.timeline = timeline;
// 	}

// 	public int Length() => values.Length;

// 	public void Execute (int index)
// 	{
// 		// var curstep = timeline.CurrentStep();
// 		// var objoftimeline = timeline._memorized_objects_list[index];
// 		// objoftimeline.Promote(curstep);
// 		// objoftimeline.PreEvaluate();
// 		// objoftimeline.AiPromotion(curstep);
// 	}
// }
