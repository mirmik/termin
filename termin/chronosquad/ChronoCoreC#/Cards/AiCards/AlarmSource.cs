abstract public class AlarmSource : EventCard<AttentionModule>
{
    public bool lures;

    public bool IsEqual(AlarmSource other)
    {
        return StartStep == other.StartStep
            && FinishStep == other.FinishStep
            && lures == other.lures;
    }

    public AlarmSource(long start_step, long final_step) : base(start_step, final_step) { }

    public abstract bool IsHighLevelAlarm();

    public bool IsAlarm(long curstep)
    {
        return curstep >= StartStep && curstep <= FinishStep;
    }

    public virtual bool IsCorpseReaction() => false;

    public abstract ReferencedPoint Center(ITimeline tl);
}
