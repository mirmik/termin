using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

enum TimelineState
{
    TS_ADD,
    TS_REMOVE,
    TS_CLEAR
}

struct CurrentTimelineGroupCommand
{
    public TimelineState state;
    public Timeline timeline;
}

public class ChronoSphere
{
    Dictionary<string, Timeline> _timelines = new Dictionary<string, Timeline>();
    Timeline _current_timeline = null;

    MyList<Timeline> _current_timelines_group = new MyList<Timeline>();
    MyList<CurrentTimelineGroupCommand> _add_buffer_current_timelines_group =
        new MyList<CurrentTimelineGroupCommand>();

    ObjectId _selected;

    MyList<PassVariant> _pass_variants = new MyList<PassVariant>();

    public NarativeState NarativeState = new NarativeState();

    //ObjectOfTimeline _selected_object = null;
    bool _pause_mode = false;
    double _time_multiplier = 1.0;
    double _measured_time_multiplier = 1.0f;
    double _time_accumulator = 0.0;
    double _target_time_in_pause_mode = 0.0;
    double _target_time_multiplier = 1.0f;

    //float last_gametime = 0.0f;
    float _chronosphere_time = 0.0f;

    public double GetAudioTimeScale()
    {
        if (Math.Abs(_time_multiplier) > 0.01f)
            return _target_time_multiplier;

        return _measured_time_multiplier;
    }

    public event Action<Timeline> OnTimelineAdded;
    public event Action<Timeline> OnTimelineDestroy;
    public event Action<ObjectOfTimeline> OnSelectedObjectChanged;

    public event Action<Timeline> OnCurrentTimelineChanged;

    public event Action<Timeline> OnTimelineToCurrentGroupAdded;
    public event Action<Timeline> OnTimelineFromCurrentGroupRemoved;
    public event Action<ObjectOfTimeline> OnObjectAddedToTimeline;
    public event Action<ObjectOfTimeline> OnObjectRemovedFromTimeline;

    List<Timeline> _timelines_choose_buffer = new List<Timeline>();

    public event Action<string> ChronosphereMessage;

    //bool _invoke_timeline_selected_signal = false;

    bool _drop_time_on_edit = false;

    //float _timestamp = 0.0f;

    //float _time_over_step = 0.0f;

    public long GlobalMinStep => 0;
    public long GlobalMaxStep => long.MaxValue;

    public MyList<Timeline> CurrentGroup => _current_timelines_group;

    Dictionary<string, AreaOfInterest> _areas_of_interest =
        new Dictionary<string, AreaOfInterest>();

    public AreaOfInterest GetOrCreateAreaOfInterest(string name)
    {
        if (_areas_of_interest.ContainsKey(name))
            return _areas_of_interest[name];

        var area = new AreaOfInterest();
        _areas_of_interest[name] = area;
        return area;
    }

    public void AddToCurrentTimelinesGroup(ITimeline tl)
    {
        if (_current_timelines_group.Contains(tl as Timeline))
            return;

        _add_buffer_current_timelines_group.Add(
            new CurrentTimelineGroupCommand
            {
                state = TimelineState.TS_ADD,
                timeline = tl as Timeline
            }
        );
    }

    public void InvokeOnObjectAdded(ObjectOfTimeline obj)
    {
        OnObjectAddedToTimeline?.Invoke(obj);
    }

    public void InvokeOnObjectRemoved(ObjectOfTimeline obj)
    {
        OnObjectRemovedFromTimeline?.Invoke(obj);
    }

    public void SetTargetTimeInPauseMode(double value)
    {
        _target_time_in_pause_mode = value;
    }

    // public void SetTimeOverStep(float value)
    // {
    // 	_time_over_step = value;
    // }

    // public float TimeOverStep()
    // {
    // 	// if (_pause_mode)
    // 	// {
    // 		return _time_over_step;
    // 	// }
    // 	// else
    // 	// {
    // 	// 	// use real time
    // 	// 	return Time.time - _timestamp;
    // 	// }
    // }

    public void RemoveFromCurrentTimelinesGroup(ITimeline tl)
    {
        _add_buffer_current_timelines_group.Add(
            new CurrentTimelineGroupCommand
            {
                state = TimelineState.TS_REMOVE,
                timeline = tl as Timeline
            }
        );
    }

    public int TimelinesCount => _timelines.Count;

    public void ClearCurrentTimelinesGroup()
    {
        _add_buffer_current_timelines_group.Add(
            new CurrentTimelineGroupCommand { state = TimelineState.TS_CLEAR, timeline = null }
        );
    }

    public bool IsDropTimeOnEdit()
    {
        return _drop_time_on_edit;
    }

    public void SetDropTimeOnEdit(bool value)
    {
        _drop_time_on_edit = value;
    }

    public void TimeReverseImmediate()
    {
        float cur_target_time_multiplier = (float)target_time_multiplier();
        set_target_time_multiplier(-cur_target_time_multiplier);
        set_time_multiplier(-cur_target_time_multiplier);
    }

    public void DestroyTimeline(Timeline tl)
    {
        _timelines.Remove(tl.Name());
        OnTimelineDestroy?.Invoke(tl);
    }

    public void modify_target_time_in_pause_mode(double deltatime)
    {
        _target_time_in_pause_mode += deltatime;
    }

    public MyList<Timeline> TimelinesList()
    {
        return new MyList<Timeline>(_timelines.Values);
    }

    public void ReturnToPreviousTimeline()
    {
        // remove current timeline
        _timelines_choose_buffer.RemoveAt(_timelines_choose_buffer.Count - 1);

        // set previous timeline
        if (_timelines_choose_buffer.Count > 0)
        {
            set_current_timeline(_timelines_choose_buffer[_timelines_choose_buffer.Count - 1]);
        }
    }

    public Timeline CreateTimeline(string name)
    {
        Timeline tl = new Timeline();
        tl.SetName(name);
        tl.SetChronosphere(this);
        AddTimeline(name, tl);
        return tl;
    }

    public Timeline CreateCopyOfCurrentTimeline()
    {
        var copy = _current_timeline.Copy();
        var name = "Timeline" + UniqueIdGenerator.GetNextId();
        copy.SetName(name);
        AddTimeline(name, copy);
        return copy;
    }

    public Timeline CreateReversedCopyOfCurrentTimeline()
    {
        var copy = _current_timeline.Copy();
        var name = "Timeline" + UniqueIdGenerator.GetNextId();
        copy.SetName(name);
        AddTimeline(name, copy);
        copy.SetReversedPass(!copy.IsReversedPass());
        copy.DropLastTimelineStep();
        copy.DropMinMaxTimelineStep();
        return copy;
    }

    public Timeline CurrentTimeline()
    {
        return _current_timeline;
    }

    public void SendMessage(string message, Int64 curstep)
    {
        ChronosphereMessage?.Invoke(message);
    }

    public void set_selected_object(ObjectOfTimeline obj)
    {
        _selected = obj.ObjectId();
        OnSelectedObjectChanged?.Invoke(obj);
    }

    public ObjectId SelectedObjectName()
    {
        return _selected;
    }

    public float time_multiplier()
    {
        return (float)_time_multiplier;
    }

    public double target_time_multiplier()
    {
        return _target_time_multiplier;
    }

    public void set_target_time_multiplier(float multiplier)
    {
        _target_time_multiplier = multiplier;
    }

    public void set_time_multiplier(double multiplier)
    {
        _time_multiplier = multiplier;
    }

    public int CountOfCards()
    {
        int count = 0;
        foreach (var tl in _timelines.Values)
        {
            count += tl.CountOfCards();
        }
        return count;
    }

    public void Select(ObjectOfTimeline obj)
    {
        if (obj.ObjectId() == _selected)
            return;

        if (obj == null)
        {
            set_selected_object(null);
            return;
        }
        set_selected_object(obj);
    }

    public bool is_pause_mode()
    {
        return _pause_mode;
    }

    public bool IsPaused()
    {
        return _pause_mode;
    }

    double _target_time_multiplier_before_pause = 1.0f;

    public void set_pause_mode(bool mode)
    {
        _pause_mode = mode;
        if (_pause_mode)
        {
            _target_time_in_pause_mode = _current_timeline.current_time();
            _target_time_multiplier_before_pause = _target_time_multiplier;
            _target_time_multiplier = 0.0f;
        }
        else
        {
            _target_time_multiplier = _target_time_multiplier_before_pause;
        }
    }

    public Timeline CreateEmptyTimeline()
    {
        var tl = new Timeline();
        AddTimeline(tl);

        if (_timelines.Count == 1)
            tl.SetCurrent();

        return tl;
    }

    public bool IsPauseMode()
    {
        return _pause_mode;
    }

    public void pause()
    {
        set_pause_mode(!is_pause_mode());
    }

    public Dictionary<string, Timeline> Timelines()
    {
        return _timelines;
    }

    public void AddTimeline(string id, Timeline timeline)
    {
        if (_timelines.ContainsKey(id))
        {
            return;
        }

        _timelines.Add(id, timeline);
        timeline.SetName(id);
        timeline.SetChronosphere(this);
        OnTimelineAdded?.Invoke(timeline);
    }

    public void RemoveTimeline(Timeline timeline)
    {
        if (timeline == null)
            return;

        _timelines.Remove(timeline.Name());
    }

    public void AddTimeline(Timeline timeline)
    {
        AddTimeline(timeline.Name(), timeline);
    }

    public Timeline current_timeline()
    {
        return _current_timeline;
    }

    public Dictionary<string, Timeline> timelines()
    {
        return _timelines;
    }

    public Timeline get_timeline_by_id(string id)
    {
        if (_timelines.ContainsKey(id))
        {
            return _timelines[id];
        }

        return null;
    }

    public void set_current_timeline(string id)
    {
        var timeline = get_timeline_by_id(id);
        set_current_timeline(timeline);
    }

    public void set_current_timeline(Timeline tl)
    {
        var old_current_timeline = _current_timeline;

        string name = tl.Name();
        if (!_timelines.ContainsKey(name))
        {
            AddTimeline(name, tl);
        }

        _current_timeline = tl;

        if (_current_timelines_group.Contains(tl)) { }
        else
        {
            RemoveFromCurrentTimelinesGroup(old_current_timeline);
            AddToCurrentTimelinesGroup(tl);
        }

        _target_time_in_pause_mode = _current_timeline.current_time();

        OnCurrentTimelineChanged?.Invoke(_current_timeline);
        _timelines_choose_buffer.Add(tl);
    }

    public int index_of_current_timeline()
    {
        int i = 0;
        foreach (var tl in _timelines.Values)
        {
            if (tl == _current_timeline)
            {
                return i;
            }
            i++;
        }
        return -1;
    }

    public void set_timeline_by_index(int index)
    {
        int i = 0;
        foreach (var tl in _timelines.Values)
        {
            if (i == index)
            {
                set_current_timeline(tl);
                return;
            }
            i++;
        }
    }

    public Timeline get_timeline_by_index(int index)
    {
        int i = 0;
        foreach (var tl in _timelines.Values)
        {
            if (i == index)
            {
                return tl;
            }
            i++;
        }
        return null;
    }

    public bool is_current_timeline(ITimeline tl)
    {
        return tl == _current_timeline;
    }

    public double rounded_to_steps(double time)
    {
        return Math.Round(time * Utility.GAME_GLOBAL_FREQUENCY) / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public void update_with_deltatime(double deltatime)
    {
        // TODO: Регуляторы надо отвязать от FPS
        // Сейчас они завязаны на FPS, и если FPS падает, то регуляторы
        // начинают работать неправильно
        var stime = CurrentTimeline().CurrentTime();

        if (is_pause_mode())
        {
            // Эта строка обеспечивает плавную доводку при остановке
            double addsig = deltatime * _time_multiplier;

            double target_time = _target_time_in_pause_mode;
            double rounded_target_time = rounded_to_steps(target_time);
            double current_time = _current_timeline.current_time();
            double diff = rounded_target_time - current_time;
            promote_deltatime(diff * 0.04 + addsig);

            _target_time_in_pause_mode += addsig;
        }
        else
        {
            promote_deltatime(deltatime * _time_multiplier);
        }

        _time_multiplier = _time_multiplier + (_target_time_multiplier - _time_multiplier) * 0.06;

        var ftime = CurrentTimeline().CurrentTime();
        var modif = (ftime - stime) / deltatime;
        if (modif != 0)
            _measured_time_multiplier = modif;
    }

    public float CurrentTimelineFlowTime()
    {
        return _current_timeline.CurrentTime();
    }

    public void UpdateForGameTime(float chronosphere_time, float deltatime)
    {
        var game_deltatime = deltatime;
        update_with_deltatime(game_deltatime);
        //last_gametime = chronosphere_time;
        this._chronosphere_time = chronosphere_time;

        var _chronosphere_step = (long)(chronosphere_time * Utility.GAME_GLOBAL_FREQUENCY);
        NarativeState.Promote(_chronosphere_step);
    }

    public void SetTargetTimeMultiplier(double tm)
    {
        _target_time_multiplier = tm;
    }

    public void promote_deltatime(double deltatime)
    {
        // if (_current_timeline == null)
        // 	return;

        // _time_accumulator += deltatime;
        // int steps = (int)(_time_accumulator * Utility.GAME_GLOBAL_FREQUENCY);
        // _time_accumulator -= ((double)steps) / Utility.GAME_GLOBAL_FREQUENCY;
        // _time_over_step = (float)_time_accumulator;
        // PromoteInc(steps);
        PromoteDelta(deltatime);
    }

    public void PromoteDelta(double deltatime)
    {
        foreach (var tl in _current_timelines_group)
        {
            tl.PromoteDelta(deltatime);
        }

        foreach (var stl in _add_buffer_current_timelines_group)
        {
            switch (stl.state)
            {
                case TimelineState.TS_ADD:
                    _current_timelines_group.Add(stl.timeline);
                    OnTimelineToCurrentGroupAdded?.Invoke(stl.timeline);
                    break;
                case TimelineState.TS_REMOVE:
                    _current_timelines_group.Remove(stl.timeline);
                    OnTimelineFromCurrentGroupRemoved?.Invoke(stl.timeline);
                    break;
                case TimelineState.TS_CLEAR:
                    _current_timelines_group.Clear();
                    break;
            }
        }

        _add_buffer_current_timelines_group.Clear();
    }

    public void PromoteInc(long steps)
    {
        foreach (var tl in _current_timelines_group)
        {
            tl.promote_steps(steps, false);
        }

        foreach (var stl in _add_buffer_current_timelines_group)
        {
            switch (stl.state)
            {
                case TimelineState.TS_ADD:
                    _current_timelines_group.Add(stl.timeline);
                    OnTimelineToCurrentGroupAdded?.Invoke(stl.timeline);
                    break;
                case TimelineState.TS_REMOVE:
                    _current_timelines_group.Remove(stl.timeline);
                    OnTimelineFromCurrentGroupRemoved?.Invoke(stl.timeline);
                    break;
                case TimelineState.TS_CLEAR:
                    _current_timelines_group.Clear();
                    break;
            }
        }

        _add_buffer_current_timelines_group.Clear();
    }

    public void NextTimeline()
    {
        int index = index_of_current_timeline();
        index++;
        if (index >= _timelines.Count)
        {
            index = 0;
        }
        set_timeline_by_index(index);
    }

    public void PrevTimeline()
    {
        int index = index_of_current_timeline();
        index--;
        if (index < 0)
        {
            index = _timelines.Count - 1;
        }
        set_timeline_by_index(index);
    }

    public void SetCurrentTimeline(Timeline tl)
    {
        set_current_timeline(tl);
    }

    public Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        var tls = new Dictionary<string, object>();
        foreach (var tl in _timelines)
        {
            tls[tl.Key] = tl.Value.ToTrent();
        }
        dict["timelines"] = tls;
        dict["current_timeline"] = _current_timeline.Name();
        dict["time_multiplier"] = _time_multiplier;
        dict["target_time_multiplier"] = _target_time_multiplier;
        dict["pause_mode"] = _pause_mode;
        dict["time_accumulator"] = _time_accumulator;
        dict["target_time_in_pause_mode"] = _target_time_in_pause_mode;
        //dict["time_over_step"] = _time_over_step;
        return dict;
    }

    public void FromTrent(Dictionary<string, object> dict)
    {
        var tls = (Dictionary<string, object>)dict["timelines"];
        foreach (var tl in tls)
        {
            var timeline = new Timeline();
            timeline.FromTrent((Dictionary<string, object>)tl.Value);
            AddTimeline(tl.Key, timeline);
        }
        set_current_timeline((string)dict["current_timeline"]);
        if (dict.ContainsKey("selected_object"))
        {
            Select(_current_timeline.GetObject((string)dict["selected_object"]));
        }
        _time_multiplier = (double)dict["time_multiplier"];
        _target_time_multiplier = (double)dict["target_time_multiplier"];
        _pause_mode = (bool)dict["pause_mode"];
        _time_accumulator = (double)dict["time_accumulator"];
        _target_time_in_pause_mode = (double)dict["target_time_in_pause_mode"];
        //_time_over_step = (float)dict["time_over_step"];
    }
}
