public abstract class PatrolStateEvent2 : EventCard<BasicAiCommander>
{
    public PatrolStateEvent2(long step) : base(step, step + 1) { }

    public PatrolStateEvent2(long sstep, long fstep) : base(sstep, fstep) { }

    protected BasicAiController Behaviour(Actor actor)
    {
        return actor.AiController() as BasicAiController;
    }

    protected AttentionModule AttentionModule(Actor actor)
    {
        return Behaviour(actor).attention_module;
    }
}
