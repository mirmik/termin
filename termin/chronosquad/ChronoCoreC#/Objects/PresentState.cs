public class PresentState : ITimeline
{
    //public Int64 _current_step = 0;
    //public float _current_time = 0;
    Timeline timeline;
    public MyList<ObjectBase> _active_objects_list = new MyList<ObjectBase>();
    public CanSee[,] _can_see_matrix = new CanSee[0, 0];
    public float[,] DistanceMatrix = new float[0, 0];
    bool _lure_component_cached = false;
    MyList<LureComponent> _lure_components_cache = new MyList<LureComponent>();

    public ObjectOfTimeline TryGetObject(string id)
    {
        return timeline.TryGetObject(id);
    }

    public Actor GetActor(ObjectId id)
    {
        return timeline.GetActor(id);
    }

    public ChronoSphere GetChronosphere()
    {
        return timeline.GetChronosphere();
    }

    public ChronoSphere GetChronoSphere()
    {
        return timeline.GetChronosphere();
    }

    public Trigger GetTrigger(long hash)
    {
        return timeline.GetTrigger(hash);
    }

    public Timeline Copy(long offset = 0, bool reverse = false)
    {
        return timeline.Copy();
    }

    public void AddDialogue(DialogueGraph dialogue, long step)
    {
        timeline.AddDialogue(dialogue, step);
    }

    public Actor GetActor(string name)
    {
        return timeline.GetActor(name);
    }

    public bool IsTimeSpirit => timeline.IsTimeSpirit;

    public ObjectOfTimeline GetObject(ObjectId id)
    {
        return timeline.GetObject(id);
    }

    public bool IsPast()
    {
        return timeline.IsPast();
    }

    public ObjectOfTimeline GetObject(long id)
    {
        return timeline.GetObject(id);
    }

    public ObjectOfTimeline GetObject(string name)
    {
        return timeline.GetObject(name);
    }

    public long CurrentStep()
    {
        return timeline.CurrentStep();
    }

    public Pose GetFrame(ObjectId frame_name)
    {
        return timeline.GetFrame(frame_name);
    }

    public bool IsReversedPass()
    {
        return timeline.IsReversedPass();
    }

    public MyList<LureComponent> LureComponentsCache()
    {
        if (!_lure_component_cached)
        {
            _lure_components_cache = new MyList<LureComponent>();
            foreach (var obj in _active_objects_list)
            {
                if (obj is Actor)
                {
                    var actor = obj as Actor;
                    var lc = actor.GetComponent<LureComponent>();
                    _lure_components_cache.Add(lc);
                }
            }
            _lure_component_cached = true;
        }
        return _lure_components_cache;
    }

    public PresentState(Timeline tl)
    {
        timeline = tl;
    }

    public PresentState(Timeline tl, PresentState ps)
    {
        timeline = tl;
        foreach (var obj in ps._active_objects_list)
            AddActiveObject(obj);
    }

    public CanSee[,] CanSeeMatrix()
    {
        return _can_see_matrix;
    }

    public CanSee GetCanSee(int i, int j)
    {
        return _can_see_matrix[i, j];
    }

    public CanSee GetCanSee(ObjectOfTimeline obj1, ObjectOfTimeline obj2)
    {
        return _can_see_matrix[obj1._timeline_index, obj2._timeline_index];
    }

    public void UpdateSightMatrixSize()
    {
        int n = _active_objects_list.Count;
        _can_see_matrix = new CanSee[n, n];
        DistanceMatrix = new float[n, n];

        for (int i = 0; i < n; ++i)
            _active_objects_list[i]._timeline_index = i;
    }

    public void AddActiveObject(ObjectBase obj, bool update_table = true)
    {
        _lure_component_cached = false;
        obj._active = true;
        obj.OnEnable();
        _active_objects_list.Add(obj);
        if (update_table)
            UpdateSightMatrixSize();
    }

    public void RemoveActiveObject(ObjectBase obj, bool update_table = true)
    {
        _lure_component_cached = false;
        obj._active = false;
        obj.OnDisable();
        _active_objects_list.Remove(obj);
        if (update_table)
            UpdateSightMatrixSize();
    }

    public void RemoveActiveObject(ObjectBase obj)
    {
        _active_objects_list.Remove(obj);
    }

    public void EvaluateDistanceMatrix()
    {
        int n = _active_objects_list.Count;
        for (int i = 0; i < n; i++)
        {
            for (int j = 0; j < i; j++)
            {
                var obj1 = _active_objects_list[i];
                var obj2 = _active_objects_list[j];
                var obj1pos = obj1.GlobalPose().position;
                var obj2pos = obj2.GlobalPose().position;
                DistanceMatrix[i, j] = (obj1pos - obj2pos).magnitude;
                DistanceMatrix[j, i] = DistanceMatrix[i, j];
            }
        }
    }

    public float Distance(int i, int j)
    {
        return DistanceMatrix[i, j];
    }

    public float Distance(ObjectOfTimeline i, ObjectOfTimeline j)
    {
        return DistanceMatrix[i._timeline_index, j._timeline_index];
    }

    public CanSee IsCanSee(int i, int j)
    {
        return _can_see_matrix[i, j];
    }

    public void ObjectStatePromotionPhase(long curstep)
    {
        foreach (var actor in timeline._memorized_objects_list)
        {
            actor.Promote(curstep);
            actor.PreEvaluate();
        }
    }

    public void ActionPhase(long curstep)
    {
        ObjectStatePromotionPhase(curstep);
        AiPromotionPhase(curstep);

        timeline.global_events.Promote(curstep, timeline);
        timeline.nondropable_global_events.Promote(curstep, timeline);
        //reversed_global_events.Promote(curstep, this);
        //reversed_nondropable_global_events.Promote(curstep, this);
        timeline.NarativeState.Promote(curstep);
    }

    void AiPromotionPhase(long curstep)
    {
        foreach (var actor in timeline._memorized_objects_list)
        {
            actor.AiPromotion(curstep);
        }
    }

    public void AddEvent(EventCard<ITimeline> ev)
    {
        timeline.AddEvent(ev);
    }

    public void AddNonDropableEvent(EventCard<ITimeline> ev)
    {
        timeline.AddNonDropableEvent(ev);
    }

    public string Name()
    {
        return timeline.Name();
    }

    public float CurrentTime()
    {
        return timeline.CurrentTime();
    }

    public MyList<ObjectOfTimeline> Heroes()
    {
        return timeline.Heroes();
    }

    public MyList<ObjectOfTimeline> Enemies()
    {
        return timeline.Enemies();
    }
}
