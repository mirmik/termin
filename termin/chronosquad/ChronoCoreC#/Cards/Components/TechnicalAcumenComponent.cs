public class TechnicalAcumenComponent : ItemComponent
{
    public TechnicalAcumenComponent(ObjectOfTimeline owner) : base(owner) { }

    public override ItemComponent Copy(ObjectOfTimeline owner)
    {
        return new TechnicalAcumenComponent(owner);
    }
}
