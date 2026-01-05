public interface ITimeline
{
    ObjectOfTimeline GetObject(ObjectId id);
    Actor GetActor(ObjectId id);
    Actor GetActor(string name);
    ObjectOfTimeline GetObject(long id);
    ObjectOfTimeline GetObject(string name);
    ObjectOfTimeline TryGetObject(string id);
    long CurrentStep();
    Pose GetFrame(ObjectId frame_name);
    bool IsReversedPass();
    void AddEvent(EventCard<ITimeline> ev);
    void AddNonDropableEvent(EventCard<ITimeline> ev);

    MyList<ObjectOfTimeline> Heroes();
    MyList<ObjectOfTimeline> Enemies();

    CanSee IsCanSee(int from, int to);

    bool IsTimeSpirit { get; }

    ///
    bool IsPast();
    string Name();

    float CurrentTime();

    ChronoSphere GetChronosphere();
    ChronoSphere GetChronoSphere();
    void AddDialogue(DialogueGraph dialogue, long step);
    Trigger GetTrigger(long hash);

    Timeline Copy(long offset = 0, bool reverse = false);
}
