public enum TimeDirection
{
    Forward,
    Backward
}

public struct Step
{
    public long step;
    public TimeDirection direction;

    public Step(long step, TimeDirection direction)
    {
        this.step = step;
        this.direction = direction;
    }
}
